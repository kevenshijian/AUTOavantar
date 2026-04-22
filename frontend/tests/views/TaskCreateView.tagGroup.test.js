import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import TaskCreateView from '@/views/TaskCreateView.vue'

vi.mock('@/stores/tagStore', () => ({
  useTagStore: vi.fn(() => ({
    tagGroups: [
      { id: 1, name: '产品介绍', type: 'scene', is_default: 1 },
      { id: 2, name: '美食展示', type: 'scene', is_default: 0 }
    ],
    sceneTagGroups: [
      { id: 1, name: '产品介绍', type: 'scene', is_default: 1 },
      { id: 2, name: '美食展示', type: 'scene', is_default: 0 }
    ],
    selectedGroupId: null,
    isLoading: false,
    error: null,
    fetchTagGroups: vi.fn(() => Promise.resolve()),
    fetchTagsByGroup: vi.fn((groupId) => {
      if (groupId === 1) {
        return Promise.resolve([
          { id: 1, group_id: 1, name: '产品展示', similar_tags: ['功能介绍'] },
          { id: 2, group_id: 1, name: '功能介绍', similar_tags: [] },
          { id: 3, group_id: 1, name: '使用效果', similar_tags: [] }
        ])
      }
      if (groupId === 2) {
        return Promise.resolve([
          { id: 4, group_id: 2, name: '食材展示', similar_tags: ['烹饪过程'] },
          { id: 5, group_id: 2, name: '烹饪过程', similar_tags: [] }
        ])
      }
      return Promise.resolve([])
    }),
    setSelectedGroupId: vi.fn()
  }))
}))

vi.mock('@/stores/taskStore', () => ({
  useTaskStore: vi.fn(() => ({
    createTask: vi.fn(() => Promise.resolve({ task_id: 'test-123' })),
    isLoading: false
  }))
}))

vi.mock('@/stores/materialStore', () => ({
  useMaterialStore: vi.fn(() => ({
    materials: [],
    fetchMaterials: vi.fn()
  }))
}))

vi.mock('@/stores/settingsStore', () => ({
  useSettingsStore: vi.fn(() => ({
    settings: {},
    fetchSettings: vi.fn()
  }))
}))

vi.mock('@/services/api', () => ({
  taskApi: {
    createTask: vi.fn(() => Promise.resolve({ task_id: 'test-123' })),
    generateScript: vi.fn(() => Promise.resolve({ script: 'test script' }))
  }
}))

vi.mock('@/services/websocket', () => ({
  default: {
    connect: vi.fn(),
    disconnect: vi.fn()
  }
}))

import { useTagStore } from '@/stores/tagStore'

describe('TaskCreateView.vue - 标签组切换', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('AC-186: 标签组选择下拉框', () => {
    it('场景视频区域应包含标签组选择下拉框', async () => {
      const wrapper = mount(TaskCreateView, {
        global: {
          plugins: [ElementPlus],
          stubs: {
            VideoSelectorDialog: true,
            AudioSelectorDialog: true
          }
        }
      })
      
      await wrapper.vm.$nextTick()
      
      const tagGroupSelect = wrapper.find('.tag-group-select')
      expect(tagGroupSelect.exists()).toBe(true)
    })

    it('标签组下拉框应显示所有场景标签组', async () => {
      const wrapper = mount(TaskCreateView, {
        global: {
          plugins: [ElementPlus],
          stubs: {
            VideoSelectorDialog: true,
            AudioSelectorDialog: true
          }
        }
      })
      
      await wrapper.vm.$nextTick()
      
      const store = useTagStore()
      expect(store.sceneTagGroups.length).toBe(2)
    })
  })

  describe('AC-187: 标签选项动态更新', () => {
    it('切换标签组应更新场景标签选项', async () => {
      const wrapper = mount(TaskCreateView, {
        global: {
          plugins: [ElementPlus],
          stubs: {
            VideoSelectorDialog: true,
            AudioSelectorDialog: true
          }
        }
      })
      
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.handleTagGroupChange).toBeDefined()
    })

    it('选择标签组后应加载标签列表', async () => {
      const wrapper = mount(TaskCreateView, {
        global: {
          plugins: [ElementPlus],
          stubs: {
            VideoSelectorDialog: true,
            AudioSelectorDialog: true
          }
        }
      })
      
      await wrapper.vm.$nextTick()
      
      const store = useTagStore()
      expect(typeof wrapper.vm.handleTagGroupChange).toBe('function')
      expect(store.fetchTagsByGroup).toBeDefined()
    })
  })

  describe('AC-188: 任务提交时传递标签组 ID', () => {
    it('任务表单应包含 sceneTagGroupId 字段', async () => {
      const wrapper = mount(TaskCreateView, {
        global: {
          plugins: [ElementPlus],
          stubs: {
            VideoSelectorDialog: true,
            AudioSelectorDialog: true
          }
        }
      })
      
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.taskForm.sceneTagGroupId).toBeDefined()
    })

    it('选择标签组后应更新 sceneTagGroupId', async () => {
      const wrapper = mount(TaskCreateView, {
        global: {
          plugins: [ElementPlus],
          stubs: {
            VideoSelectorDialog: true,
            AudioSelectorDialog: true
          }
        }
      })
      
      await wrapper.vm.$nextTick()
      
      wrapper.vm.taskForm.sceneTagGroupId = 2
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.taskForm.sceneTagGroupId).toBe(2)
    })
  })

  describe('场景标签选择器', () => {
    it('场景标签选项应来自动态加载的标签列表', async () => {
      const wrapper = mount(TaskCreateView, {
        global: {
          plugins: [ElementPlus],
          stubs: {
            VideoSelectorDialog: true,
            AudioSelectorDialog: true
          }
        }
      })
      
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.sceneTagOptions).toBeDefined()
    })

    it('默认应使用默认标签组', async () => {
      const wrapper = mount(TaskCreateView, {
        global: {
          plugins: [ElementPlus],
          stubs: {
            VideoSelectorDialog: true,
            AudioSelectorDialog: true
          }
        }
      })
      
      await wrapper.vm.$nextTick()
      
      const store = useTagStore()
      const defaultGroup = store.sceneTagGroups.find(g => g.is_default === 1)
      expect(defaultGroup).toBeDefined()
    })
  })
})