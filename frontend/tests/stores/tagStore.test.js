import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTagStore } from '@/stores/tagStore'

vi.mock('@/services/api', () => ({
  tagApi: {
    getTagGroups: vi.fn(() => Promise.resolve({ groups: [] })),
    createTagGroup: vi.fn((data) => Promise.resolve({ id: 1, name: data.name, type: 'scene' })),
    updateTagGroup: vi.fn((id, data) => Promise.resolve({ id, name: data.name })),
    deleteTagGroup: vi.fn(() => Promise.resolve({ deleted: true })),
    getTagsByGroup: vi.fn(() => Promise.resolve({ tags: [] })),
    addTagToGroup: vi.fn((groupId, data) => Promise.resolve({ id: 1, group_id: groupId, name: data.name })),
    updateTag: vi.fn((tagId, data) => Promise.resolve({ id: tagId, name: data.name })),
    deleteTag: vi.fn(() => Promise.resolve({ deleted: true })),
    getEmotionTags: vi.fn(() => Promise.resolve({ emotions: [] })),
    createEmotionTag: vi.fn((data) => Promise.resolve({ id: 1, name: data.name })),
    updateEmotionTag: vi.fn((tagId, data) => Promise.resolve({ id: tagId, name: data.name })),
    deleteEmotionTag: vi.fn(() => Promise.resolve({ deleted: true })),
    syncEmotionsToYaml: vi.fn(() => Promise.resolve({ synced: true }))
  }
}))

import { tagApi } from '@/services/api'

describe('tagStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('AC-178: 标签组状态管理', () => {
    it('store 应包含 tagGroups 状态', () => {
      const store = useTagStore()
      expect(store.tagGroups).toBeDefined()
      expect(Array.isArray(store.tagGroups)).toBe(true)
    })

    it('store 应包含 selectedGroupId 状态', () => {
      const store = useTagStore()
      expect(store.selectedGroupId).toBeDefined()
      expect(store.selectedGroupId).toBeNull()
    })

    it('store 应包含 emotionTags 状态', () => {
      const store = useTagStore()
      expect(store.emotionTags).toBeDefined()
      expect(Array.isArray(store.emotionTags)).toBe(true)
    })
  })

  describe('AC-186: 获取标签组列表', () => {
    it('store 应提供 fetchTagGroups 方法', () => {
      const store = useTagStore()
      expect(typeof store.fetchTagGroups).toBe('function')
    })

    it('fetchTagGroups 应调用 API 并更新 tagGroups', async () => {
      const mockGroups = [
        { id: 1, name: '产品介绍', type: 'scene', is_default: 1 },
        { id: 2, name: '美食展示', type: 'scene', is_default: 0 }
      ]
      tagApi.getTagGroups.mockResolvedValueOnce({ groups: mockGroups })

      const store = useTagStore()
      await store.fetchTagGroups()

      expect(tagApi.getTagGroups).toHaveBeenCalled()
      expect(store.tagGroups).toEqual(mockGroups)
    })
  })

  describe('AC-187: 获取标签组内的标签', () => {
    it('store 应提供 fetchTagsByGroup 方法', () => {
      const store = useTagStore()
      expect(typeof store.fetchTagsByGroup).toBe('function')
    })

    it('fetchTagsByGroup 应调用 API 并返回标签列表', async () => {
      const mockTags = [
        { id: 1, group_id: 1, name: '产品展示', similar_tags: ['功能介绍'] },
        { id: 2, group_id: 1, name: '功能介绍', similar_tags: [] }
      ]
      tagApi.getTagsByGroup.mockResolvedValueOnce({ tags: mockTags })

      const store = useTagStore()
      const result = await store.fetchTagsByGroup(1)

      expect(tagApi.getTagsByGroup).toHaveBeenCalledWith(1)
      expect(result).toEqual(mockTags)
    })
  })

  describe('AC-179: 创建标签组', () => {
    it('store 应提供 createTagGroup 方法', () => {
      const store = useTagStore()
      expect(typeof store.createTagGroup).toBe('function')
    })

    it('createTagGroup 应调用 API 并更新 tagGroups', async () => {
      const newGroup = { id: 3, name: '服务介绍', type: 'scene' }
      tagApi.createTagGroup.mockResolvedValueOnce(newGroup)

      const store = useTagStore()
      store.tagGroups = [{ id: 1, name: '产品介绍' }]
      
      const result = await store.createTagGroup({ name: '服务介绍', type: 'scene' })

      expect(tagApi.createTagGroup).toHaveBeenCalledWith({ name: '服务介绍', type: 'scene' })
      expect(store.tagGroups).toContainEqual(newGroup)
      expect(result).toEqual(newGroup)
    })
  })

  describe('AC-180: 更新标签组', () => {
    it('store 应提供 updateTagGroup 方法', () => {
      const store = useTagStore()
      expect(typeof store.updateTagGroup).toBe('function')
    })

    it('updateTagGroup 应调用 API 并更新本地状态', async () => {
      const updatedGroup = { id: 1, name: '产品展示（更新）' }
      tagApi.updateTagGroup.mockResolvedValueOnce(updatedGroup)

      const store = useTagStore()
      store.tagGroups = [{ id: 1, name: '产品介绍' }]

      await store.updateTagGroup(1, { name: '产品展示（更新）' })

      expect(tagApi.updateTagGroup).toHaveBeenCalledWith(1, { name: '产品展示（更新）' })
      expect(store.tagGroups[0].name).toBe('产品展示（更新）')
    })
  })

  describe('AC-181: 删除标签组', () => {
    it('store 应提供 deleteTagGroup 方法', () => {
      const store = useTagStore()
      expect(typeof store.deleteTagGroup).toBe('function')
    })

    it('deleteTagGroup 应调用 API 并从 tagGroups 中移除', async () => {
      tagApi.deleteTagGroup.mockResolvedValueOnce({ deleted: true })

      const store = useTagStore()
      store.tagGroups = [{ id: 1, name: '产品介绍' }, { id: 2, name: '美食展示' }]

      await store.deleteTagGroup(1)

      expect(tagApi.deleteTagGroup).toHaveBeenCalledWith(1)
      expect(store.tagGroups).toHaveLength(1)
      expect(store.tagGroups[0].id).toBe(2)
    })
  })

  describe('AC-182: 标签 CRUD', () => {
    it('store 应提供 addTagToGroup 方法', () => {
      const store = useTagStore()
      expect(typeof store.addTagToGroup).toBe('function')
    })

    it('store 应提供 updateTag 方法', () => {
      const store = useTagStore()
      expect(typeof store.updateTag).toBe('function')
    })

    it('store 应提供 deleteTag 方法', () => {
      const store = useTagStore()
      expect(typeof store.deleteTag).toBe('function')
    })

    it('addTagToGroup 应调用 API', async () => {
      const newTag = { id: 3, group_id: 1, name: '使用效果', similar_tags: [] }
      tagApi.addTagToGroup.mockResolvedValueOnce(newTag)

      const store = useTagStore()
      const result = await store.addTagToGroup(1, { name: '使用效果', similar_tags: [] })

      expect(tagApi.addTagToGroup).toHaveBeenCalledWith(1, { name: '使用效果', similar_tags: [] })
      expect(result).toEqual(newTag)
    })
  })

  describe('AC-183: 情绪标签状态管理', () => {
    it('store 应提供 fetchEmotionTags 方法', () => {
      const store = useTagStore()
      expect(typeof store.fetchEmotionTags).toBe('function')
    })

    it('fetchEmotionTags 应调用 API 并更新 emotionTags', async () => {
      const mockEmotions = [
        { id: 1, name: '开心', vec1: 0.3, speed: 1.04 },
        { id: 2, name: '生气', vec2: 0.3, speed: 1.06 }
      ]
      tagApi.getEmotionTags.mockResolvedValueOnce({ emotions: mockEmotions })

      const store = useTagStore()
      await store.fetchEmotionTags()

      expect(tagApi.getEmotionTags).toHaveBeenCalled()
      expect(store.emotionTags).toEqual(mockEmotions)
    })
  })

  describe('AC-184: 情绪标签 CRUD', () => {
    it('store 应提供 createEmotionTag 方法', () => {
      const store = useTagStore()
      expect(typeof store.createEmotionTag).toBe('function')
    })

    it('store 应提供 updateEmotionTag 方法', () => {
      const store = useTagStore()
      expect(typeof store.updateEmotionTag).toBe('function')
    })

    it('store 应提供 deleteEmotionTag 方法', () => {
      const store = useTagStore()
      expect(typeof store.deleteEmotionTag).toBe('function')
    })

    it('createEmotionTag 应调用 API 并更新 emotionTags', async () => {
      const newEmotion = { id: 3, name: '期待', vec1: 0.2, vec7: 0.3, speed: 1.05 }
      tagApi.createEmotionTag.mockResolvedValueOnce(newEmotion)

      const store = useTagStore()
      store.emotionTags = [{ id: 1, name: '开心' }]
      
      await store.createEmotionTag({ name: '期待', vec1: 0.2, vec7: 0.3, speed: 1.05 })

      expect(tagApi.createEmotionTag).toHaveBeenCalled()
      expect(store.emotionTags).toContainEqual(newEmotion)
    })
  })

  describe('AC-185: 情绪标签同步到 YAML', () => {
    it('store 应提供 syncEmotionsToYaml 方法', () => {
      const store = useTagStore()
      expect(typeof store.syncEmotionsToYaml).toBe('function')
    })

    it('syncEmotionsToYaml 应调用 API', async () => {
      tagApi.syncEmotionsToYaml.mockResolvedValueOnce({ synced: true, count: 5 })

      const store = useTagStore()
      const result = await store.syncEmotionsToYaml()

      expect(tagApi.syncEmotionsToYaml).toHaveBeenCalled()
      expect(result.synced).toBe(true)
    })
  })

  describe('选中标签组管理', () => {
    it('store 应提供 setSelectedGroupId 方法', () => {
      const store = useTagStore()
      expect(typeof store.setSelectedGroupId).toBe('function')
    })

    it('setSelectedGroupId 应更新 selectedGroupId', () => {
      const store = useTagStore()
      store.setSelectedGroupId(1)
      expect(store.selectedGroupId).toBe(1)
    })
  })

  describe('加载状态管理', () => {
    it('store 应包含 isLoading 状态', () => {
      const store = useTagStore()
      expect(store.isLoading).toBeDefined()
      expect(store.isLoading).toBe(false)
    })

    it('store 应包含 error 状态', () => {
      const store = useTagStore()
      expect(store.error).toBeDefined()
      expect(store.error).toBeNull()
    })
  })
})