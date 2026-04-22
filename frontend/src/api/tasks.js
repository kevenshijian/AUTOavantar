import apiClient from './index'

export const taskAPI = {
  /**
   * 创建新任务
   * @param {Object} taskData - 任务数据
   * @returns {Promise<Object>} 创建的任务信息
   */
  createTask(taskData) {
    return apiClient.post('/tasks', taskData)
  },

  /**
   * 获取任务列表
   * @param {string} status - 可选的任务状态过滤
   * @returns {Promise<Array>} 任务列表
   */
  getTasks(status) {
    const params = status ? { status } : {}
    return apiClient.get('/tasks', { params })
  },

  /**
   * 获取任务详情
   * @param {string} taskId - 任务ID
   * @returns {Promise<Object>} 任务详情
   */
  getTask(taskId) {
    return apiClient.get(`/tasks/${taskId}`)
  },

  /**
   * 获取任务状态（轮询接口）
   * @param {string} taskId - 任务ID
   * @returns {Promise<Object>} 任务状态信息
   */
  getTaskStatus(taskId) {
    return apiClient.get(`/tasks/${taskId}/status`)
  },

  /**
   * 删除任务
   * @param {string} taskId - 任务ID
   * @returns {Promise<Object>} 删除结果
   */
  deleteTask(taskId) {
    return apiClient.delete(`/tasks/${taskId}`)
  }
}

export default taskAPI
