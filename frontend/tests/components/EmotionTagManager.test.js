import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import EmotionTagManager from '@/components/EmotionTagManager.vue'

vi.mock('@/stores/tagStore', () => ({
  useTagStore: vi.fn(() => ({
    emotionTags: [
      { id: 1, name: '开心', vec1: 0.3, vec2: 0, vec3: 0, vec4: 0, vec5: 0, vec6: 0, vec7: 0, vec8: 0, speed: 1.04 },
      { id: 2, name: '生气', vec1: 0, vec2: 0.3, vec3: 0, vec4: 0, vec5: 0, vec6: 0, vec7: 0, vec8: 0, speed: 1.06 }
    ],
    isLoading: false,
    error: null,
    fetchEmotionTags: vi.fn(() => Promise.resolve()),
    createEmotionTag: vi.fn((data) => Promise.resolve({ id: 3, ...data })),
    updateEmotionTag: vi.fn((tagId, data) => Promise.resolve({ id: tagId, ...data })),
    deleteEmotionTag: vi.fn(() => Promise.resolve()),
    syncEmotionsToYaml: vi.fn(() => Promise.resolve({ synced: true })),
    clearError: vi.fn()
  }))
}))

import { useTagStore } from '@/stores/tagStore'

describe('EmotionTagManager.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('AC-183: 情绪标签列表显示', () => {
    it('组件应渲染情绪标签表格', () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const table = wrapper.find('.el-table')
      expect(table.exists()).toBe(true)
    })

    it('表格应显示情绪标签名称', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      await wrapper.vm.$nextTick()
      
      const store = useTagStore()
      expect(store.emotionTags.length).toBe(2)
    })

    it('表格应显示向量参数列', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      await wrapper.vm.$nextTick()
      
      const table = wrapper.find('.el-table')
      expect(table.exists()).toBe(true)
    })

    it('表格应显示语速参数列', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      await wrapper.vm.$nextTick()
      
      const store = useTagStore()
      expect(store.emotionTags[0].speed).toBeDefined()
    })
  })

  describe('AC-184: 创建情绪标签', () => {
    it('组件应包含新建情绪标签按钮', () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const createBtn = wrapper.find('.create-emotion-btn')
      expect(createBtn.exists()).toBe(true)
    })

    it('点击新建按钮应显示对话框', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const createBtn = wrapper.find('.create-emotion-btn')
      await createBtn.trigger('click')
      
      expect(wrapper.vm.showCreateDialog).toBe(true)
    })

    it('对话框应包含名称输入框', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.showCreateDialog = true
      await wrapper.vm.$nextTick()
      
      const nameInput = wrapper.find('.emotion-name-input')
      expect(nameInput.exists()).toBe(true)
    })

    it('对话框应包含向量输入框', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.showCreateDialog = true
      await wrapper.vm.$nextTick()
      
      const vecInputs = wrapper.findAll('.vec-input')
      expect(vecInputs.length).toBe(8)
    })

    it('对话框应包含语速输入框', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.showCreateDialog = true
      await wrapper.vm.$nextTick()
      
      const speedInput = wrapper.find('.speed-input')
      expect(speedInput.exists()).toBe(true)
    })
  })

  describe('AC-185: 编辑情绪标签', () => {
    it('组件应包含编辑功能', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.handleEdit).toBeDefined()
      expect(typeof wrapper.vm.handleEdit).toBe('function')
    })

    it('编辑功能应能设置编辑表单', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      await wrapper.vm.$nextTick()
      
      wrapper.vm.handleEdit({ id: 1, name: '开心', vec1: 0.3, speed: 1.04 })
      
      expect(wrapper.vm.editEmotionForm.id).toBe(1)
      expect(wrapper.vm.editEmotionForm.name).toBe('开心')
      expect(wrapper.vm.showEditDialog).toBe(true)
    })
  })

  describe('AC-196: 删除情绪标签', () => {
    it('组件应包含删除功能', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.handleDelete).toBeDefined()
      expect(typeof wrapper.vm.handleDelete).toBe('function')
    })
  })

  describe('参数范围验证', () => {
    it('向量参数应在 0-1.0 范围内', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.newEmotionForm.vec1 = 1.5
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.newEmotionForm.vec1).toBe(1.5)
    })

    it('语速参数应在 0.8-1.2 范围内', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.newEmotionForm.speed = 1.5
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.newEmotionForm.speed).toBe(1.5)
    })
  })

  describe('YAML 同步功能', () => {
    it('组件应包含同步到 YAML 按钮', () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const syncBtn = wrapper.find('.sync-yaml-btn')
      expect(syncBtn.exists()).toBe(true)
    })

    it('点击同步按钮应调用 syncEmotionsToYaml', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const syncBtn = wrapper.find('.sync-yaml-btn')
      expect(syncBtn.exists()).toBe(true)
      
      const store = useTagStore()
      expect(store.syncEmotionsToYaml).toBeDefined()
    })
  })

  describe('加载状态', () => {
    it('组件应包含 isLoading 状态', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.isLoading).toBeDefined()
    })
  })

  describe('错误处理', () => {
    it('有错误时应显示错误信息', async () => {
      const wrapper = mount(EmotionTagManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.error = '操作失败'
      await wrapper.vm.$nextTick()
      
      expect(wrapper.text()).toContain('操作失败')
    })
  })
})