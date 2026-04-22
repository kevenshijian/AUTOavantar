import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTaskStore } from '@/stores/taskStore'

vi.mock('@/services/api', () => ({
  taskApi: {
    getTasks: vi.fn(() => Promise.resolve({ data: { items: [] } })),
    getTask: vi.fn(() => Promise.resolve({ task_id: 'test-123', status: 'processing', progress: 50 })),
    createTask: vi.fn(() => Promise.resolve({ task_id: 'test-123' })),
    deleteTask: vi.fn(() => Promise.resolve()),
    control: vi.fn(() => Promise.resolve())
  }
}))

vi.mock('@/services/websocket', () => ({
  default: {
    connect: vi.fn(() => Promise.resolve()),
    disconnect: vi.fn(),
    onStatusUpdate: vi.fn(() => vi.fn()),
    onCompleted: vi.fn(() => vi.fn()),
    onFailed: vi.fn(() => vi.fn()),
    isConnected: vi.fn(() => false)
  }
}))

import websocketService from '@/services/websocket'

describe('taskStore WebSocket 集成', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('AC-115: WebSocket 连接方法', () => {
    it('store 应提供 connectWebSocket 方法', () => {
      const store = useTaskStore()
      expect(typeof store.connectWebSocket).toBe('function')
    })

    it('connectWebSocket 应调用 websocketService.connect', async () => {
      const store = useTaskStore()
      store.tasks = [{ task_id: 'test-123', status: 'processing' }]
      
      await store.connectWebSocket('test-123')
      
      expect(websocketService.connect).toHaveBeenCalledWith('test-123')
    })
  })

  describe('AC-123: 状态更新同步', () => {
    it('store 应提供 updateTaskFromWebSocket 方法', () => {
      const store = useTaskStore()
      expect(typeof store.updateTaskFromWebSocket).toBe('function')
    })

    it('updateTaskFromWebSocket 应更新任务状态', () => {
      const store = useTaskStore()
      store.tasks = [{ task_id: 'test-123', status: 'processing', progress: 50 }]
      
      store.updateTaskFromWebSocket({
        task_id: 'test-123',
        status: 'completed',
        progress: 100,
        stage: '完成'
      })
      
      expect(store.tasks[0].status).toBe('completed')
      expect(store.tasks[0].progress).toBe(100)
    })
  })

  describe('WebSocket 生命周期管理', () => {
    it('store 应提供 disconnectWebSocket 方法', () => {
      const store = useTaskStore()
      expect(typeof store.disconnectWebSocket).toBe('function')
    })

    it('disconnectWebSocket 应调用 websocketService.disconnect', () => {
      const store = useTaskStore()
      store.disconnectWebSocket()
      
      expect(websocketService.disconnect).toHaveBeenCalled()
    })
  })
})
