import { defineStore } from 'pinia'
import { tagApi } from '@/services/api'

export const useTagStore = defineStore('tags', {
  state: () => ({
    tagGroups: [],
    emotionTags: [],
    selectedGroupId: null,
    isLoading: false,
    error: null
  }),

  getters: {
    selectedGroup: (state) => {
      if (!state.selectedGroupId) return null
      return state.tagGroups.find(g => g.id === state.selectedGroupId) || null
    },
    
    sceneTagGroups: (state) => {
      return state.tagGroups.filter(g => g.type === 'scene')
    },
    
    emotionTagGroups: (state) => {
      return state.tagGroups.filter(g => g.type === 'emotion')
    },
    
    defaultTagGroup: (state) => {
      return state.tagGroups.find(g => g.is_default === 1) || null
    }
  },

  actions: {
    setSelectedGroupId(groupId) {
      this.selectedGroupId = groupId
    },

    async fetchTagGroups() {
      this.isLoading = true
      this.error = null
      
      try {
        const response = await tagApi.getTagGroups()
        this.tagGroups = response.groups || []
        return this.tagGroups
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async fetchTagsByGroup(groupId) {
      this.isLoading = true
      this.error = null
      
      try {
        const response = await tagApi.getTagsByGroup(groupId)
        return response.tags || []
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async createTagGroup(data) {
      this.isLoading = true
      this.error = null
      
      try {
        const newGroup = await tagApi.createTagGroup(data)
        // 重新加载确保数据完整一致
        await this.fetchTagGroups()
        return newGroup
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async updateTagGroup(groupId, data) {
      this.isLoading = true
      this.error = null
      
      try {
        const updatedGroup = await tagApi.updateTagGroup(groupId, data)
        const index = this.tagGroups.findIndex(g => g.id === groupId)
        if (index !== -1) {
          this.tagGroups[index] = { ...this.tagGroups[index], ...updatedGroup }
        }
        return updatedGroup
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async deleteTagGroup(groupId) {
      this.isLoading = true
      this.error = null
      
      try {
        await tagApi.deleteTagGroup(groupId)
        this.tagGroups = this.tagGroups.filter(g => g.id !== groupId)
        
        if (this.selectedGroupId === groupId) {
          this.selectedGroupId = null
        }
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async addTagToGroup(groupId, data) {
      this.isLoading = true
      this.error = null
      
      try {
        const newTag = await tagApi.addTagToGroup(groupId, data)
        return newTag
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async updateTag(tagId, data) {
      this.isLoading = true
      this.error = null
      
      try {
        const updatedTag = await tagApi.updateTag(tagId, data)
        return updatedTag
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async deleteTag(tagId) {
      this.isLoading = true
      this.error = null
      
      try {
        await tagApi.deleteTag(tagId)
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async fetchEmotionTags() {
      this.isLoading = true
      this.error = null
      
      try {
        const response = await tagApi.getEmotionTags()
        this.emotionTags = response.emotions || []
        return this.emotionTags
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async createEmotionTag(data) {
      this.isLoading = true
      this.error = null
      
      try {
        const newEmotion = await tagApi.createEmotionTag(data)
        this.emotionTags.push(newEmotion)
        return newEmotion
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async updateEmotionTag(tagId, data) {
      this.isLoading = true
      this.error = null
      
      try {
        const updatedEmotion = await tagApi.updateEmotionTag(tagId, data)
        const index = this.emotionTags.findIndex(e => e.id === tagId)
        if (index !== -1) {
          this.emotionTags[index] = { ...this.emotionTags[index], ...updatedEmotion }
        }
        return updatedEmotion
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async deleteEmotionTag(tagId) {
      this.isLoading = true
      this.error = null
      
      try {
        await tagApi.deleteEmotionTag(tagId)
        this.emotionTags = this.emotionTags.filter(e => e.id !== tagId)
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async syncEmotionsToYaml() {
      this.isLoading = true
      this.error = null
      
      try {
        const result = await tagApi.syncEmotionsToYaml()
        return result
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    clearError() {
      this.error = null
    }
  }
})