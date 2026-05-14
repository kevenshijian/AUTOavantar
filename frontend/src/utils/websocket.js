/**
 * WebSocket 连接管理器
 * 实现单例模式，提供自动重连、心跳检测、消息订阅等功能
 */

class WebSocketManager {
  constructor() {
    // 单例模式检查
    if (WebSocketManager.instance) {
      return WebSocketManager.instance;
    }

    /**
     * 存储WebSocket连接实例
     */
    this.ws = null;
    
    /**
     * 连接配置
     */
    this.config = {
      url: '',
      reconnectInterval: 3000,  // 重连间隔(毫秒)
      maxReconnectAttempts: 5,  // 最大重连次数
      heartbeatInterval: 30000, // 心跳间隔(毫秒)
    };

    /**
     * 连接状态
     */
    this.state = {
      isConnected: false,
      reconnectAttempts: 0,
      shouldReconnect: true,
    };

    /**
     * 定时器
     */
    this.timers = {
      reconnect: null,
      heartbeat: null,
    };

    /**
     * 消息处理器集合
     */
    this.messageHandlers = new Map();

    WebSocketManager.instance = this;
  }

  /**
   * 获取单例实例
   */
  static getInstance() {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager();
    }
    return WebSocketManager.instance;
  }

  /**
   * 建立WebSocket连接
   * @param {string} url - WebSocket服务器地址
   * @param {Object} options - 配置选项
   */
  connect(url, options = {}) {
    if (this.ws && this.state.isConnected) {
      console.log('[WebSocket] 已连接，无需重复连接');
      return this;
    }

    this.config.url = url;
    Object.assign(this.config, options);
    this.state.shouldReconnect = true;
    this.state.reconnectAttempts = 0;

    this._createConnection();
    return this;
  }

  /**
   * 创建WebSocket连接
   * @private
   */
  _createConnection() {
    try {
      console.log(`[WebSocket] 正在连接: ${this.config.url}`);
      
      this.ws = new WebSocket(this.config.url);

      this.ws.onopen = (event) => {
        console.log('[WebSocket] 连接成功');
        this.state.isConnected = true;
        this.state.reconnectAttempts = 0;
        
        // 启动心跳
        this._startHeartbeat();
        
        // 触发连接成功事件
        this._emit('connected', event);
      };

      this.ws.onmessage = (event) => {
        this._handleMessage(event.data);
      };

      this.ws.onerror = (error) => {
        console.error('[WebSocket] 连接错误:', error);
        this._emit('error', error);
      };

      this.ws.onclose = (event) => {
        console.log('[WebSocket] 连接关闭:', event.code, event.reason);
        this.state.isConnected = false;
        this._stopHeartbeat();
        this._emit('disconnected', event);

        // 自动重连
        if (this.state.shouldReconnect) {
          this._attemptReconnect();
        }
      };

    } catch (error) {
      console.error('[WebSocket] 创建连接失败:', error);
      this._attemptReconnect();
    }
  }

  /**
   * 尝试重新连接
   * @private
   */
  _attemptReconnect() {
    if (this.state.reconnectAttempts >= this.config.maxReconnectAttempts) {
      console.error('[WebSocket] 重连次数已达上限，停止重连');
      this._emit('reconnect_failed');
      return;
    }

    this.state.reconnectAttempts++;
    console.log(`[WebSocket] ${this.config.reconnectInterval}ms后尝试第${this.state.reconnectAttempts}次重连...`);

    this.timers.reconnect = setTimeout(() => {
      this._createConnection();
    }, this.config.reconnectInterval);
  }

  /**
   * 启动心跳检测
   * @private
   */
  _startHeartbeat() {
    this._stopHeartbeat();
    
    this.timers.heartbeat = setInterval(() => {
      if (this.state.isConnected) {
        this.send({ type: 'ping', timestamp: Date.now() });
      }
    }, this.config.heartbeatInterval);
  }

  /**
   * 停止心跳检测
   * @private
   */
  _stopHeartbeat() {
    if (this.timers.heartbeat) {
      clearInterval(this.timers.heartbeat);
      this.timers.heartbeat = null;
    }
  }

  /**
   * 处理收到的消息
   * @private
   * @param {string} data - 消息数据
   */
  _handleMessage(data) {
    try {
      const message = JSON.parse(data);
      
      // 处理心跳响应
      if (message.type === 'pong') {
        console.log('[WebSocket] 收到心跳响应');
        return;
      }

      console.log('[WebSocket] 收到消息:', message);
      
      // 根据消息类型分发
      if (message.type) {
        this._emit(message.type, message.data || message);
      }
      
      // 触发通用消息事件
      this._emit('message', message);
      
    } catch (error) {
      console.log('[WebSocket] 收到原始消息:', data);
      this._emit('message', data);
    }
  }

  /**
   * 发送消息
   * @param {Object|string} data - 要发送的数据
   */
  send(data) {
    if (!this.state.isConnected) {
      console.warn('[WebSocket] 未连接，无法发送消息');
      return false;
    }

    const message = typeof data === 'string' ? data : JSON.stringify(data);
    
    try {
      this.ws.send(message);
      return true;
    } catch (error) {
      console.error('[WebSocket] 发送消息失败:', error);
      return false;
    }
  }

  /**
   * 订阅消息
   * @param {string} event - 事件类型
   * @param {Function} handler - 处理函数
   */
  on(event, handler) {
    if (!this.messageHandlers.has(event)) {
      this.messageHandlers.set(event, new Set());
    }
    this.messageHandlers.get(event).add(handler);
    
    // 返回取消订阅函数
    return () => this.off(event, handler);
  }

  /**
   * 取消订阅
   * @param {string} event - 事件类型
   * @param {Function} handler - 处理函数
   */
  off(event, handler) {
    if (this.messageHandlers.has(event)) {
      this.messageHandlers.get(event).delete(handler);
    }
  }

  /**
   * 触发事件
   * @private
   * @param {string} event - 事件类型
   * @param {*} data - 事件数据
   */
  _emit(event, data) {
    if (this.messageHandlers.has(event)) {
      this.messageHandlers.get(event).forEach(handler => {
        try {
          handler(data);
        } catch (error) {
          console.error(`[WebSocket] 事件处理错误 (${event}):`, error);
        }
      });
    }
  }

  /**
   * 断开连接
   * @param {boolean} reconnect - 是否允许自动重连
   */
  disconnect(reconnect = false) {
    this.state.shouldReconnect = reconnect;
    
    // 清除重连定时器
    if (this.timers.reconnect) {
      clearTimeout(this.timers.reconnect);
      this.timers.reconnect = null;
    }

    this._stopHeartbeat();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.state.isConnected = false;
    console.log('[WebSocket] 已断开连接');
  }

  /**
   * 获取连接状态
   */
  getConnectionState() {
    return {
      isConnected: this.state.isConnected,
      reconnectAttempts: this.state.reconnectAttempts,
      url: this.config.url,
    };
  }
}

// 导出单例实例
export const wsManager = WebSocketManager.getInstance();

// 导出类
export default WebSocketManager;
