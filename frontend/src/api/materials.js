import apiClient from './index'

export const materialAPI = {
  /**
   * 获取角色列表
   * @returns {Promise<Array>} 角色列表
   */
  getRoles() {
    return apiClient.get('/materials/roles')
  },

  /**
   * 获取角色详情
   * @param {string} roleId - 角色ID
   * @returns {Promise<Object>} 角色详情
   */
  getRole(roleId) {
    return apiClient.get(`/materials/roles/${roleId}`)
  },

  /**
   * 获取场景列表
   * @param {string} sceneType - 可选的场景类型过滤
   * @returns {Promise<Array>} 场景列表
   */
  getScenes(sceneType) {
    const params = sceneType ? { scene_type: sceneType } : {}
    return apiClient.get('/materials/scenes', { params })
  },

  /**
   * 获取场景详情
   * @param {string} sceneId - 场景ID
   * @returns {Promise<Object>} 场景详情
   */
  getScene(sceneId) {
    return apiClient.get(`/materials/scenes/${sceneId}`)
  },

  /**
   * 获取 BGM 列表
   * @returns {Promise<Array>} BGM 列表
   */
  getBGM() {
    return apiClient.get('/materials/bgm')
  },

  /**
   * 获取 BGM 详情
   * @param {string} bgmId - BGM ID
   * @returns {Promise<Object>} BGM 详情
   */
  getBGMDetail(bgmId) {
    return apiClient.get(`/materials/bgm/${bgmId}`)
  }
}

export default materialAPI
