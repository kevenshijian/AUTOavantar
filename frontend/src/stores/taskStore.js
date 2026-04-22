import { defineStore } from 'pinia'
import { taskApi } from '@/services/api'
import websocketService from '@/services/websocket'

export const useTaskStore = defineStore('tasks', {
  state: () => ({
    tasks: [],
    currentTask: null,
    isLoading: false,
    error: null,
    pollingTimer: null,
    pollingInterval: 3000,
    websocketUnsubscribes: [],
    isPageVisible: true,
    visibilityChangeHandler: null
  }),

  getters: {
    pendingTasks: (state) => (Array.isArray(state.tasks) ? state.tasks.filter(t => t.status === 'pending') : []),
    processingTasks: (state) => (Array.isArray(state.tasks) ? state.tasks.filter(t => t.status === 'processing') : []),
    completedTasks: (state) => (Array.isArray(state.tasks) ? state.tasks.filter(t => t.status === 'completed') : []),
    failedTasks: (state) => (Array.isArray(state.tasks) ? state.tasks.filter(t => t.status === 'failed') : []),
    pendingCount: (state) => (Array.isArray(state.tasks) ? state.tasks.filter(t => 
      t.status === 'pending' || t.status === 'processing'
    ).length : 0)
  },

  actions: {
    /**
     * 创建新任务
     */
    async createTask(taskData) {
      this.isLoading = true
      this.error = null
      
      try {
        const apiResponse = await taskApi.createTask(taskData)
        const taskResult = apiResponse.data || apiResponse
        if (taskResult) {
          this.tasks.unshift(taskResult)
        }
        return taskResult
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 获取所有任务
     */
    async fetchTasks() {
      this.isLoading = true
      this.error = null
      
      try {
        const apiResponse = await taskApi.getTasks()
        this.tasks = (apiResponse.data && apiResponse.data.items) || (apiResponse.data || [])
      } catch (error) {
        this.error = error.message
        this.tasks = []
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 获取单个任务详情
     */
    async fetchTask(taskId) {
      this.isLoading = true
      this.error = null
      
      try {
        const response = await taskApi.getTask(taskId)
        this.currentTask = response
        
        const index = this.tasks.findIndex(t => t.task_id === taskId)
        if (index !== -1) {
          this.tasks[index] = response
        }
        
        return response
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 获取任务状态（轮询）
     */
    async pollTaskStatus(taskId) {
      try {
        const response = await taskApi.getTask(taskId)
        
        const index = this.tasks.findIndex(t => t.task_id === taskId)
        if (index !== -1) {
          this.tasks[index] = { ...this.tasks[index], ...response }
        }
        
        if (this.currentTask?.task_id === taskId) {
          this.currentTask = { ...this.currentTask, ...response }
        }
        
        return response
      } catch (error) {
        console.error(`轮询任务 ${taskId} 状态失败:`, error)
      }
    },

    /**
     * 启动轮询
     */
    startPolling() {
      if (this.pollingTimer) {
        return
      }

      // 初始化页面可见性监听
      if (!this.visibilityChangeHandler) {
        this.visibilityChangeHandler = () => {
          this.isPageVisible = !document.hidden
          if (this.isPageVisible && !this.pollingTimer) {
            // 页面重新可见时恢复轮询
            this.startPolling()
          }
        }
        document.addEventListener('visibilitychange', this.visibilityChangeHandler)
      }

      const poll = () => {
        // 页面不可见时暂停轮询
        if (!this.isPageVisible) {
          this.pollingTimer = null
          return
        }

        // 确保tasks是数组
        const tasksArray = Array.isArray(this.tasks) ? this.tasks : []
        const runningTasks = tasksArray.filter(t =>
          ['pending', 'queued', 'running', 'processing'].includes(t.status)
        )

        if (runningTasks.length > 0) {
          runningTasks.forEach(task => {
            this.pollTaskStatus(task.task_id)
          })
        }

        this.pollingTimer = setTimeout(poll, this.pollingInterval)
      }

      poll()
    },

    /**
     * 停止轮询
     */
    stopPolling() {
      if (this.pollingTimer) {
        clearTimeout(this.pollingTimer)
        this.pollingTimer = null
      }
      if (this.visibilityChangeHandler) {
        document.removeEventListener('visibilitychange', this.visibilityChangeHandler)
        this.visibilityChangeHandler = null
      }
    },

    /**
     * 删除任务
     */
    async deleteTask(taskId) {
      this.isLoading = true
      this.error = null
      
      try {
        await taskApi.deleteTask(taskId)
        this.tasks = this.tasks.filter(t => t.task_id !== taskId)
        
        if (this.currentTask?.task_id === taskId) {
          this.currentTask = null
        }
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 设置轮询间隔
     */
    setPollingInterval(interval) {
      this.pollingInterval = interval
    },

    /**
     * 生成文案
     */
    async generateScript({ topic, prompt, mode }) {
      this.isLoading = true
      this.error = null
      
      try {
        const response = await taskApi.generateScript({ topic, prompt, mode })
        return response
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 从视频中提取音频
     */
    async extractAudio(videoPath) {
      this.isLoading = true
      this.error = null
      
      try {
        const response = await taskApi.extractAudio(videoPath)
        return response
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 音频降噪
     */
    async denoiseAudio(audioId) {
      this.isLoading = true
      this.error = null
      
      try {
        const response = await taskApi.denoiseAudio(audioId)
        return response
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 面部分析
     */
    async analyzeFace(videoId) {
      console.log('开始面部分析，视频ID:', videoId)
      this.isLoading = true
      this.error = null
      
      try {
        const response = await taskApi.analyzeFace(videoId)
        console.log('面部分析成功，响应:', response)
        return response
      } catch (error) {
        console.error('面部分析失败:', error)
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
        console.log('面部分析结束，isLoading重置为false')
      }
    },

    /**
     * 清除错误
     */
    clearError() {
      this.error = null
    },

    /**
     * 连接 WebSocket
     */
    async connectWebSocket(taskId) {
      try {
        await websocketService.connect(taskId)
      } catch (error) {
        console.error(`连接任务 ${taskId} WebSocket 失败:`, error)
      }
    },

    /**
     * 断开 WebSocket
     */
    disconnectWebSocket() {
      this.websocketUnsubscribes.forEach(unsubscribe => unsubscribe())
      this.websocketUnsubscribes = []
      websocketService.disconnect()
    },

    /**
     * 从 WebSocket 消息更新任务状态
     */
    updateTaskFromWebSocket(message) {
      const index = this.tasks.findIndex(t => t.task_id === message.task_id)
      if (index !== -1) {
        // 使用$patch更新数组，确保响应式
        this.$patch(state => {
          state.tasks[index] = {
            ...state.tasks[index],
            status: message.status,
            progress: message.progress,
            current_stage: message.stage || message.current_stage || state.tasks[index].current_stage,
            output_path: message.output_path || state.tasks[index].output_path,
            error_message: message.error_message || message.message || state.tasks[index].error_message
          }
        })
        console.log(`任务状态已更新: task_id=${message.task_id}, status=${message.status}, progress=${message.progress}, stage=${message.stage}`)
      }
      
      if (this.currentTask?.task_id === message.task_id) {
        this.$patch(state => {
          state.currentTask = {
            ...state.currentTask,
            ...message
          }
        })
      }
    },

    /**
     * 设置 WebSocket 监听器
     */
    setupWebSocketListeners() {
      const unsubscribeStatus = websocketService.onStatusUpdate((message) => {
        this.updateTaskFromWebSocket(message)
      })
      this.websocketUnsubscribes.push(unsubscribeStatus)

      const unsubscribeCompleted = websocketService.onCompleted((message) => {
        this.updateTaskFromWebSocket({
          task_id: message.task_id,
          status: 'completed',
          progress: 100,
          output_path: message.output_path
        })
      })
      this.websocketUnsubscribes.push(unsubscribeCompleted)

      const unsubscribeFailed = websocketService.onFailed((message) => {
        this.updateTaskFromWebSocket({
          task_id: message.task_id,
          status: 'failed',
          error_message: message.message || message.error_message
        })
      })
      this.websocketUnsubscribes.push(unsubscribeFailed)
    },

    /**
     * 连接所有运行中任务的 WebSocket
     */
    async connectRunningTasks() {
      const runningTasks = this.tasks.filter(t => 
        ['pending', 'processing', 'running', 'queued'].includes(t.status)
      )
      
      for (const task of runningTasks) {
        await this.connectWebSocket(task.task_id)
      }
    }
  }
})