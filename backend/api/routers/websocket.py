"""
WebSocket 路由
提供实时任务状态推送
"""

import logging
import asyncio
from typing import Dict, Set
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

logger = logging.getLogger("websocket")

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 按 task_id 存储连接
        self.connections: Dict[str, Set[WebSocket]] = {}
        # 存储所有连接的最后活跃时间
        self.last_activity: Dict[WebSocket, datetime] = {}
        # 存储等待连接的任务（用于竞态条件处理）
        self._pending_connections: Dict[str, asyncio.Event] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """建立连接"""
        await websocket.accept()

        if task_id not in self.connections:
            self.connections[task_id] = set()

        self.connections[task_id].add(websocket)
        self.last_activity[websocket] = datetime.now()

        logger.info(f"WebSocket 连接建立: task_id={task_id}, 当前连接数: {len(self.connections[task_id])}")

        # 通知等待此任务连接的协程
        if task_id in self._pending_connections:
            self._pending_connections[task_id].set()

        # 发送欢迎消息
        await self.send_message(websocket, {
            "type": "connected",
            "task_id": task_id,
            "message": "连接成功"
        })
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        """断开连接"""
        if task_id in self.connections:
            self.connections[task_id].discard(websocket)
            if not self.connections[task_id]:
                del self.connections[task_id]
        
        if websocket in self.last_activity:
            del self.last_activity[websocket]
        
        logger.info(f"WebSocket 连接断开: task_id={task_id}")
    
    async def send_message(self, websocket: WebSocket, message: dict):
        """发送消息给单个连接"""
        try:
            await websocket.send_json(message)
            self.last_activity[websocket] = datetime.now()
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    async def broadcast_to_task(self, task_id: str, message: dict):
        """广播消息给指定任务的所有连接"""
        logger.info(f"broadcast_to_task: task_id={task_id}, connections={self.connections.get(task_id, set())}")
        
        if task_id not in self.connections:
            logger.warning(f"broadcast_to_task: 没有找到 task_id={task_id} 的连接")
            return
        
        disconnected = []
        sent_count = 0
        for websocket in self.connections[task_id]:
            try:
                await websocket.send_json(message)
                self.last_activity[websocket] = datetime.now()
                sent_count += 1
                logger.info(f"broadcast_to_task: 消息已发送到 websocket, task_id={task_id}")
            except Exception as e:
                logger.error(f"广播消息失败: {e}")
                disconnected.append(websocket)
        
        logger.info(f"broadcast_to_task: 共发送 {sent_count} 条消息, task_id={task_id}")
        
        for websocket in disconnected:
            self.disconnect(websocket, task_id)
    
    async def broadcast_status_update(
        self,
        task_id: str,
        status: str,
        progress: float,
        stage: str = "",
        message: str = "",
        output_path: str = None,
        **kwargs
    ):
        """广播状态更新"""
        data = {
            "type": "status_update",
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "stage": stage,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

        if output_path:
            data["output_path"] = output_path

        data.update(kwargs)

        logger.info(f"broadcast_status_update: 准备发送, task_id={task_id}, status={status}, progress={progress}")
        await self.broadcast_to_task(task_id, data)
        logger.info(f"broadcast_status_update: 发送完成, task_id={task_id}")
    
    async def send_heartbeat(self, websocket: WebSocket):
        """发送心跳"""
        try:
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat()
            })
        except Exception:
            pass
    
    async def check_inactive_connections(self, timeout_seconds: int = 60):
        """检查并关闭不活跃的连接"""
        now = datetime.now()
        to_disconnect = []
        
        for websocket, last_time in self.last_activity.items():
            if (now - last_time).total_seconds() > timeout_seconds:
                to_disconnect.append(websocket)
        
        for websocket in to_disconnect:
            # 找到对应的 task_id
            for task_id, connections in self.connections.items():
                if websocket in connections:
                    try:
                        await websocket.close()
                    except Exception:
                        pass
                    self.disconnect(websocket, task_id)
                    logger.info(f"关闭不活跃连接: task_id={task_id}")
                    break

    async def wait_for_connection(self, task_id: str, timeout: float = 3.0) -> bool:
        """
        等待指定任务的 WebSocket 连接建立

        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）

        Returns:
            是否在超时前建立了连接
        """
        # 如果已有连接，直接返回
        if task_id in self.connections and self.connections[task_id]:
            return True

        # 创建等待事件
        if task_id not in self._pending_connections:
            self._pending_connections[task_id] = asyncio.Event()

        try:
            # 等待连接建立或超时
            await asyncio.wait_for(
                self._pending_connections[task_id].wait(),
                timeout=timeout
            )
            return True
        except asyncio.TimeoutError:
            logger.warning(f"等待 WebSocket 连接超时: task_id={task_id}")
            return False
        finally:
            # 清理等待事件
            if task_id in self._pending_connections:
                del self._pending_connections[task_id]


# 全局连接管理器
manager = ConnectionManager()


async def notify_task_status(task_id: str, status: str, progress: float, stage: str = "", message: str = ""):
    """
    通知任务状态更新
    
    供工作流服务调用
    
    Args:
        task_id: 任务ID
        status: 任务状态
        progress: 进度 (0-100)
        stage: 当前阶段
        message: 消息
    """
    await manager.broadcast_status_update(task_id, status, progress, stage, message)


@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket 端点
    
    客户端连接后，可以实时接收任务状态更新
    
    Args:
        websocket: WebSocket 连接
        task_id: 任务ID
    """
    await manager.connect(websocket, task_id)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            
            # 更新活跃时间
            manager.last_activity[websocket] = datetime.now()
            
            # 处理客户端消息
            try:
                import json
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "ping":
                    # 心跳响应
                    await manager.send_heartbeat(websocket)
                
                elif msg_type == "subscribe":
                    # 订阅消息（可以扩展）
                    await manager.send_message(websocket, {
                        "type": "subscribed",
                        "task_id": task_id
                    })
                
                else:
                    await manager.send_message(websocket, {
                        "type": "error",
                        "message": f"未知消息类型: {msg_type}"
                    })
                    
            except json.JSONDecodeError:
                await manager.send_message(websocket, {
                    "type": "error",
                    "message": "无效的 JSON 格式"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        manager.disconnect(websocket, task_id)