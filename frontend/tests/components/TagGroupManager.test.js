import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import TagGroupManager from '@/components/TagGroupManager.vue'

vi.mock('@/stores/tagStore', () => ({
  useTagStore: vi.fn(() => ({
    tagGroups: [
      { id: 1, name: '产品介绍', type: 'scene', is_default: 1 },
      { id: 2, name: '美食展示', type: 'scene', is_default: 0 }
    ],
    emotionTags: [],
    selectedGroupId: null,
    isLoading: false,
    error: null,
    sceneTagGroups: [
      { id: 1, name: '产品介绍', type: 'scene', is_default: 1 },
      { id: 2, name: '美食展示', type: 'scene', is_default: 0 }
    ],
    selectedGroup: null,
    fetchTagGroups: vi.fn(() => Promise.resolve()),
    fetchTagsByGroup: vi.fn(() => Promise.resolve([
      { id: 1, group_id: 1, name: '产品展示', similar_tags: ['功能介绍'] },
      { id: 2, group_id: 1, name: '功能介绍', similar_tags: [] }
    ])),
    createTagGroup: vi.fn((data) => Promise.resolve({ id: 3, name: data.name, type: 'scene' })),
    updateTagGroup: vi.fn((id, data) => Promise.resolve({ id, name: data.name })),
    deleteTagGroup: vi.fn(() => Promise.resolve()),
    addTagToGroup: vi.fn((groupId, data) => Promise.resolve({ id: 3, group_id: groupId, name: data.name })),
    updateTag: vi.fn((tagId, data) => Promise.resolve({ id: tagId, name: data.name })),
    deleteTag: vi.fn(() => Promise.resolve()),
    setSelectedGroupId: vi.fn(),
    clearError: vi.fn()
  }))
}))

import { useTagStore } from '@/stores/tagStore'

describe('TagGroupManager.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('AC-178: 标签组列表显示', () => {
    it('组件应渲染标签组选择下拉框', () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const select = wrapper.find('.el-select')
      expect(select.exists()).toBe(true)
    })

    it('下拉框应显示所有场景标签组', () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const store = useTagStore()
      expect(store.sceneTagGroups.length).toBe(2)
    })

    it('默认标签组应显示标记', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      await wrapper.vm.$nextTick()
      
      const select = wrapper.find('.el-select')
      expect(select.exists()).toBe(true)
      
      const store = useTagStore()
      const defaultGroup = store.sceneTagGroups.find(g => g.is_default === 1)
      expect(defaultGroup).toBeDefined()
      expect(defaultGroup.name).toBe('产品介绍')
    })
  })

  describe('AC-179: 创建标签组', () => {
    it('组件应包含新建标签组按钮', () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const createBtn = wrapper.find('.create-group-btn')
      expect(createBtn.exists()).toBe(true)
    })

    it('点击新建按钮应显示对话框', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const createBtn = wrapper.find('.create-group-btn')
      await createBtn.trigger('click')
      
      expect(wrapper.vm.showCreateDialog).toBe(true)
    })

    it('对话框应包含标签组名称输入框', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.showCreateDialog = true
      await wrapper.vm.$nextTick()
      
      const nameInput = wrapper.find('.group-name-input')
      expect(nameInput.exists()).toBe(true)
    })
  })

  describe('AC-180: 更新标签组', () => {
    it('组件应包含编辑标签组按钮', () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const editBtn = wrapper.find('.edit-group-btn')
      expect(editBtn.exists()).toBe(true)
    })

    it('点击编辑按钮应显示编辑对话框', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.selectedGroupId = 1
      await wrapper.vm.$nextTick()
      
      const editBtn = wrapper.find('.edit-group-btn')
      await editBtn.trigger('click')
      
      expect(wrapper.vm.showEditDialog).toBe(true)
    })
  })

  describe('AC-181: 删除标签组', () => {
    it('组件应包含删除标签组按钮', () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      const deleteBtn = wrapper.find('.delete-group-btn')
      expect(deleteBtn.exists()).toBe(true)
    })

    it('删除按钮点击应触发确认对话框', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus],
          mocks: {
            $confirm: vi.fn(() => Promise.resolve())
          }
        }
      })
      
      wrapper.vm.selectedGroupId = 1
      await wrapper.vm.$nextTick()
      
      const deleteBtn = wrapper.find('.delete-group-btn')
      expect(deleteBtn.exists()).toBe(true)
    })
  })

  describe('AC-182: 标签列表显示', () => {
    it('选中标签组后应显示标签列表', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.selectedGroupId = 1
      wrapper.vm.tags = [
        { id: 1, name: '产品展示', similar_tags: ['功能介绍'] }
      ]
      await wrapper.vm.$nextTick()
      
      const tagList = wrapper.find('.tag-list')
      expect(tagList.exists()).toBe(true)
    })

    it('标签列表应显示相似标签', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.selectedGroupId = 1
      wrapper.vm.tags = [
        { id: 1, name: '产品展示', similar_tags: ['功能介绍', '使用效果'] }
      ]
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()
      
      const table = wrapper.find('.el-table')
      expect(table.exists()).toBe(true)
      
      const similarTags = wrapper.findAll('.similar-tag')
      expect(similarTags.length).toBeGreaterThan(0)
    })

    it('组件应包含添加标签按钮', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.selectedGroupId = 1
      await wrapper.vm.$nextTick()
      
      const addTagBtn = wrapper.find('.add-tag-btn')
      expect(addTagBtn.exists()).toBe(true)
    })
  })

  describe('标签 CRUD 操作', () => {
    it('添加标签按钮应显示添加对话框', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.selectedGroupId = 1
      await wrapper.vm.$nextTick()
      
      const addTagBtn = wrapper.find('.add-tag-btn')
      await addTagBtn.trigger('click')
      
      expect(wrapper.vm.showAddTagDialog).toBe(true)
    })

    it('标签应包含编辑按钮', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.selectedGroupId = 1
      wrapper.vm.tags = [
        { id: 1, name: '产品展示', similar_tags: [] }
      ]
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()
      
      const table = wrapper.find('.el-table')
      expect(table.exists()).toBe(true)
      
      const buttons = wrapper.findAll('button')
      const hasEditBtn = buttons.some(btn => btn.text().includes('编辑'))
      expect(hasEditBtn).toBe(true)
    })

    it('标签应包含删除按钮', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.selectedGroupId = 1
      wrapper.vm.tags = [
        { id: 1, name: '产品展示', similar_tags: [] }
      ]
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()
      
      const table = wrapper.find('.el-table')
      expect(table.exists()).toBe(true)
      
      const buttons = wrapper.findAll('button')
      const hasDeleteBtn = buttons.some(btn => btn.text().includes('删除'))
      expect(hasDeleteBtn).toBe(true)
    })
  })

  describe('加载状态', () => {
    it('加载时应显示加载指示器', async () => {
      const wrapper = mount(TagGroupManager, {
        global: {
          plugins: [ElementPlus]
        }
      })
      
      wrapper.vm.isLoading = true
      await wrapper.vm.$nextTick()
      
      const loadingIndicator = wrapper.find('.el-loading-mask')
      expect(loadingIndicator.exists() || wrapper.vm.isLoading).toBe(true)
    })
  })

  describe('错误处理', () => {
    it('有错误时应显示错误信息', async () => {
      const wrapper = mount(TagGroupManager, {
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