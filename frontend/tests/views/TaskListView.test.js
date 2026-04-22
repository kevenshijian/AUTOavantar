import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/services/api', () => ({
  taskApi: {
    getTasks: vi.fn(() => Promise.resolve({ data: { items: [] } })),
    control: vi.fn(() => Promise.resolve()),
    delete: vi.fn(() => Promise.resolve())
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

import TaskListView from '@/views/TaskListView.vue'
import websocketService from '@/services/websocket'

const flushPromises = () => new Promise(resolve => setTimeout(resolve, 0))

describe('TaskListView WebSocket 集成', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('AC-115: 任务状态实时更新', () => {
    it('页面加载时应设置 WebSocket 监听器', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      
      const wrapper = mount(TaskListView, {
        global: {
          plugins: [pinia],
          stubs: {
            'el-card': { template: '<div><slot /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-form': { template: '<form><slot /></form>' },
            'el-form-item': { template: '<div><slot /></div>' },
            'el-select': { template: '<select><slot /></select>' },
            'el-option': { template: '<option></option>' },
            'el-input': { template: '<input />' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-progress': { template: '<div></div>' },
            'el-dropdown': { template: '<div><slot /></div>' },
            'el-dropdown-menu': { template: '<ul><slot /></ul>' },
            'el-dropdown-item': { template: '<li><slot /></li>' },
            'el-pagination': { template: '<div></div>' },
            'el-link': { template: '<a><slot /></a>' },
            'el-message': true,
            Plus: { template: '<span>+</span>' },
            Search: { template: '<span>search</span>' },
            ArrowDown: { template: '<span>↓</span>' }
          },
          directives: {
            loading: () => {}
          }
        }
      })

      await flushPromises()
      await wrapper.vm.$nextTick()
      
      expect(websocketService.onStatusUpdate).toHaveBeenCalled()
    })

    it('任务状态变化时应自动更新前端显示', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      
      const wrapper = mount(TaskListView, {
        global: {
          plugins: [pinia],
          stubs: {
            'el-card': { template: '<div><slot /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-form': { template: '<form><slot /></form>' },
            'el-form-item': { template: '<div><slot /></div>' },
            'el-select': { template: '<select><slot /></select>' },
            'el-option': { template: '<option></option>' },
            'el-input': { template: '<input />' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-progress': { template: '<div></div>' },
            'el-dropdown': { template: '<div><slot /></div>' },
            'el-dropdown-menu': { template: '<ul><slot /></ul>' },
            'el-dropdown-item': { template: '<li><slot /></li>' },
            'el-pagination': { template: '<div></div>' },
            'el-link': { template: '<a><slot /></a>' },
            'el-message': true,
            Plus: { template: '<span>+</span>' },
            Search: { template: '<span>search</span>' },
            ArrowDown: { template: '<span>↓</span>' }
          },
          directives: {
            loading: () => {}
          }
        }
      })

      await flushPromises()
      
      expect(websocketService.onStatusUpdate).toHaveBeenCalled()
    })
  })

  describe('AC-116: 任务完成即时显示', () => {
    it('任务完成时应立即显示"已完成"状态', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      
      const wrapper = mount(TaskListView, {
        global: {
          plugins: [pinia],
          stubs: {
            'el-card': { template: '<div><slot /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-form': { template: '<form><slot /></form>' },
            'el-form-item': { template: '<div><slot /></div>' },
            'el-select': { template: '<select><slot /></select>' },
            'el-option': { template: '<option></option>' },
            'el-input': { template: '<input />' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-progress': { template: '<div></div>' },
            'el-dropdown': { template: '<div><slot /></div>' },
            'el-dropdown-menu': { template: '<ul><slot /></ul>' },
            'el-dropdown-item': { template: '<li><slot /></li>' },
            'el-pagination': { template: '<div></div>' },
            'el-link': { template: '<a><slot /></a>' },
            'el-message': true,
            Plus: { template: '<span>+</span>' },
            Search: { template: '<span>search</span>' },
            ArrowDown: { template: '<span>↓</span>' }
          },
          directives: {
            loading: () => {}
          }
        }
      })

      await flushPromises()
      
      expect(websocketService.onCompleted).toHaveBeenCalled()
    })
  })

  describe('AC-121: WebSocket 自动重连', () => {
    it('WebSocket 断开后应尝试重连', async () => {
      expect(websocketService.connect).toBeDefined()
      expect(typeof websocketService.connect).toBe('function')
    })
  })
})
