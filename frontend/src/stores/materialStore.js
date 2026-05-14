import { defineStore } from 'pinia'
import { materialApi } from '@/services/api'

export const useMaterialStore = defineStore('material', {
  state: () => ({
    materials: {
      roles: [],
      scenes: [],
      audios: [],
      bgm: []
    },
    isLoading: false,
    error: null
  }),

  getters: {
    allMaterials: (state) => {
      return [
        ...state.materials.roles,
        ...state.materials.scenes,
        ...state.materials.audios,
        ...state.materials.bgm
      ]
    },
    
    getMaterialById: (state) => (id) => {
      return state.allMaterials.find(m => m.id === id)
    }
  },

  actions: {
    /**
     * 加载所有素材
     */
    async loadMaterials() {
      this.isLoading = true
      this.error = null
      
      try {
        console.log('=== materialStore.loadMaterials 开始 ===')
        // 并行加载所有类型的素材
        const [roles, scenes, audios, bgm] = await Promise.all([
          materialApi.getMaterials('role').catch(() => []),
          materialApi.getMaterials('scene').catch(() => []),
          materialApi.getMaterials('audio').catch(() => []),
          materialApi.getMaterials('bgm').catch(() => [])
        ])
        
        console.log('原始 roles 响应:', roles)
        console.log('roles 类型:', typeof roles)
        console.log('roles 是否数组:', Array.isArray(roles))
        if (Array.isArray(roles) && roles.length > 0) {
          console.log('第一个角色数据:', roles[0])
          console.log('第一个角色的所有键:', Object.keys(roles[0]))
        }
        
        // 处理数据，统一ID和名称字段
        const processMaterial = (item, idField, nameField) => ({
          ...item,
          id: item[idField] || item.id,
          name: item[nameField] || item.name
        })
        
        const processedRoles = (roles || []).map(r => processMaterial(r, 'role_id', 'role_name'))
        const processedScenes = (scenes || []).map(s => processMaterial(s, 'scene_id', 'scene_name'))
        const processedAudios = (audios || []).map(a => processMaterial(a, 'id', 'name'))
        const processedBgm = (bgm || []).map(b => processMaterial(b, 'bgm_id', 'bgm_name'))
        
        console.log('处理后的 processedRoles:', processedRoles)
        if (processedRoles.length > 0) {
          console.log('处理后的第一个角色:', processedRoles[0])
          console.log('处理后的第一个角色的 is_double_mode:', processedRoles[0].is_double_mode)
        }
        
        this.materials = {
          roles: processedRoles,
          scenes: processedScenes,
          audios: processedAudios,
          bgm: processedBgm
        }
      } catch (error) {
        this.error = error.message
        console.error('加载素材失败:', error)
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 获取素材详情
     */
    async fetchMaterial(materialId) {
      this.isLoading = true
      this.error = null
      
      try {
        const response = await materialApi.getMaterial(materialId)
        return response
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 上传素材
     */
    async uploadMaterial(formData) {
      this.isLoading = true
      this.error = null
      
      try {
        const response = await materialApi.uploadMaterial(formData)
        // 刷新素材列表
        await this.loadMaterials()
        return response
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 删除素材
     */
    async deleteMaterial(materialId, type = 'audio') {
      this.isLoading = true
      this.error = null
      
      try {
        await materialApi.delete(materialId, type)
        // 刷新素材列表
        await this.loadMaterials()
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 清除错误
     */
    clearError() {
      this.error = null
    }
  }
})
