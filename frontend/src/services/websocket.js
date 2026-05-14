/**
 * WebSocket 客户端服务
 * 用于实时接收任务状态更新
 * 支持多任务连接
 */

class WebSocketService {
  constructor() {
    this.connections = new Map();
    this.callbacks = new Map();
    this.reconnectAttempts = new Map();
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;
    this.heartbeatIntervals = new Map();
    this.visibilityChangeHandler = null;
    this.isPageVisible = true;
  }

  initVisibilityHandler() {
    if (this.visibilityChangeHandler) return;

    this.visibilityChangeHandler = () => {
      this.isPageVisible = !document.hidden;

      if (this.isPageVisible) {
        console.log('[WebSocket] 页面重新可见，尝试恢复连接');
        this.reconnectVisibleTasks();
      } else {
        console.log('[WebSocket] 页面进入后台，暂停心跳');
      }
    };

    document.addEventListener('visibilitychange', this.visibilityChangeHandler);
  }

  reconnectVisibleTasks() {
    console.log('[WebSocket] reconnectVisibleTasks 被调用');
    console.log('[WebSocket] 当前连接状态:', this.getConnectedTasks());
    console.log('[WebSocket] connections Map 大小:', this.connections.size);

    // 获取所有需要重连的任务 ID
    const tasksToReconnect = [];

    this.connections.forEach((ws, taskId) => {
      const state = ws.readyState;
      console.log(`[WebSocket] 检查连接: task_id=${taskId}, readyState=${state} (CONNECTING=0, OPEN=1, CLOSING=2, CLOSED=3)`);

      if (state !== WebSocket.OPEN) {
        tasksToReconnect.push(taskId);
      }
    });

    // 清理并重连
    tasksToReconnect.forEach(taskId => {
      console.log(`[WebSocket] 准备重连: task_id=${taskId}`);

      // 先清理旧连接
      const oldWs = this.connections.get(taskId);
      if (oldWs) {
        // 移除旧的事件处理器，防止触发重连逻辑
        oldWs.onopen = null;
        oldWs.onmessage = null;
        oldWs.onerror = null;
        oldWs.onclose = null;

        // 如果连接还在关闭中或已关闭，直接删除
        if (oldWs.readyState === WebSocket.CLOSED || oldWs.readyState === WebSocket.CLOSING) {
          this.connections.delete(taskId);
        }
      }

      // 重新连接
      this.connect(taskId).catch(err => {
        console.error(`[WebSocket] 恢复连接失败: task_id=${taskId}`, err);
      });
    });
  }

  connect(taskId) {
    return new Promise((resolve, reject) => {
      // 检查是否已有打开的连接
      if (this.connections.has(taskId)) {
        const existingWs = this.connections.get(taskId);
        if (existingWs.readyState === WebSocket.OPEN) {
          console.log(`WebSocket 已连接: task_id=${taskId}`);
          resolve();
          return;
        } else {
          // 清理旧连接
          console.log(`[WebSocket] 清理旧连接: task_id=${taskId}, readyState=${existingWs.readyState}`);
          existingWs.onopen = null;
          existingWs.onmessage = null;
          existingWs.onerror = null;
          existingWs.onclose = null;
          this.connections.delete(taskId);
        }
      }

      const wsUrl = `ws://localhost:9010/api/ws/${taskId}`;
      console.log(`[WebSocket] 正在连接: ${wsUrl}`);

      try {
        const ws = new WebSocket(wsUrl);
        this.connections.set(taskId, ws);
        this.reconnectAttempts.set(taskId, 0);

        ws.onopen = () => {
          console.log(`WebSocket 连接成功: task_id=${taskId}`);
          this.reconnectAttempts.set(taskId, 0);
          this.startHeartbeat(taskId);
          resolve();
        };

        ws.onmessage = (event) => {
          this.handleMessage(taskId, event.data);
        };

        ws.onerror = (error) => {
          console.error(`WebSocket 错误 (task_id=${taskId}):`, error);
          reject(error);
        };

        ws.onclose = (event) => {
          console.log(`WebSocket 连接关闭 (task_id=${taskId}):`, event.code, event.reason);
          this.stopHeartbeat(taskId);

          // 只在页面可见且非正常关闭时尝试重连
          if (event.code !== 1000 && this.isPageVisible) {
            this.attemptReconnect(taskId);
          }
        };
      } catch (error) {
        console.error(`WebSocket 连接失败 (task_id=${taskId}):`, error);
        reject(error);
      }
    });
  }

  handleMessage(taskId, data) {
    try {
      const message = JSON.parse(data);
      
      if (message.type === 'heartbeat') {
        return;
      }

      this.callbacks.forEach((callback, key) => {
        const lastUnderscoreIndex = key.lastIndexOf('_');
        const type = key.substring(0, lastUnderscoreIndex);
        const cbTaskId = key.substring(lastUnderscoreIndex + 1);
        
        if (cbTaskId === taskId || cbTaskId === '*') {
          let shouldExecute = false;
          
          if (type === '*' || type === message.type) {
            shouldExecute = true;
          } else if (message.type === 'status_update') {
            if (type === 'completed' && message.status === 'completed') {
              shouldExecute = true;
            } else if (type === 'failed' && message.status === 'failed') {
              shouldExecute = true;
            }
          }
          
          if (shouldExecute) {
            console.log(`[WebSocket] 执行回调: key=${key}, message=`, message);
            callback(message);
          }
        }
      });
    } catch (error) {
      console.error('[WebSocket] 解析消息失败:', error);
    }
  }

  subscribe(type, taskId, callback) {
    const key = `${type}_${taskId}`;
    this.callbacks.set(key, callback);
    
    return () => {
      this.callbacks.delete(key);
    };
  }

  onStatusUpdate(callback) {
    return this.subscribe('status_update', '*', callback);
  }

  onConnected(callback) {
    return this.subscribe('connected', '*', callback);
  }

  onCompleted(callback) {
    return this.subscribe('completed', '*', callback);
  }

  onFailed(callback) {
    return this.subscribe('failed', '*', callback);
  }

  sendHeartbeat(taskId) {
    const ws = this.connections.get(taskId);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    }
  }

  startHeartbeat(taskId) {
    this.stopHeartbeat(taskId);
    const interval = setInterval(() => {
      if (this.isPageVisible) {
        this.sendHeartbeat(taskId);
      }
    }, 30000);
    this.heartbeatIntervals.set(taskId, interval);
  }

  stopHeartbeat(taskId) {
    if (this.heartbeatIntervals.has(taskId)) {
      clearInterval(this.heartbeatIntervals.get(taskId));
      this.heartbeatIntervals.delete(taskId);
    }
  }

  attemptReconnect(taskId) {
    const attempts = this.reconnectAttempts.get(taskId) || 0;
    if (attempts >= this.maxReconnectAttempts) {
      console.error(`WebSocket 重连次数已达上限 (task_id=${taskId})`);
      return;
    }

    this.reconnectAttempts.set(taskId, attempts + 1);
    console.log(`WebSocket 尝试重连 (task_id=${taskId}, ${attempts + 1}/${this.maxReconnectAttempts})...`);

    setTimeout(() => {
      this.connect(taskId).catch((error) => {
        console.error(`重连失败 (task_id=${taskId}):`, error);
      });
    }, this.reconnectDelay);
  }

  disconnect(taskId) {
    this.stopHeartbeat(taskId);
    
    if (this.connections.has(taskId)) {
      const ws = this.connections.get(taskId);
      ws.close(1000, 'Manual disconnect');
      this.connections.delete(taskId);
    }
    
    console.log(`WebSocket 已断开 (task_id=${taskId})`);
  }

  disconnectAll() {
    this.connections.forEach((ws, taskId) => {
      this.disconnect(taskId);
    });
    this.callbacks.clear();

    if (this.visibilityChangeHandler) {
      document.removeEventListener('visibilitychange', this.visibilityChangeHandler);
      this.visibilityChangeHandler = null;
    }

    console.log('所有 WebSocket 连接已断开');
  }

  isConnected(taskId) {
    return this.connections.has(taskId) && 
           this.connections.get(taskId).readyState === WebSocket.OPEN;
  }

  getConnectedTasks() {
    const tasks = [];
    this.connections.forEach((ws, taskId) => {
      if (ws.readyState === WebSocket.OPEN) {
        tasks.push(taskId);
      }
    });
    return tasks;
  }
}

const websocketService = new WebSocketService();

export default websocketService;
