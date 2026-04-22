import apiClient from './index'

export const uploadAPI = {
  /**
   * 上传视频文件
   * @param {File} file - 视频文件
   * @param {string} groupType - 视频分组类型: opening/loop/scene/ending
   * @param {string} purpose - 上传目的: material=创建素材, task=创建任务
   * @returns {Promise<Object>} 上传结果
   */
  uploadVideo(file, groupType = 'scene', purpose = 'material') {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('group_type', groupType)
    formData.append('purpose', purpose)

    return apiClient.post('/upload/video', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  /**
   * 上传音频文件
   * @param {File} file - 音频文件
   * @param {string} audioType - 音频类型: reference/prompt/bgm
   * @param {Function} onProgress - 上传进度回调函数
   * @returns {Promise<Object>} 上传结果
   */
  uploadAudio(file, audioType = 'reference', onProgress = null) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('audio_type', audioType)

    return apiClient.post('/upload/audio', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percentCompleted)
        }
      }
    })
  }
}

export default uploadAPI
