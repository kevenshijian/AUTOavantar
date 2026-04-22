import axios from 'axios'

const MAX_RETRIES = 5
const RETRY_DELAY = 2000

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms))

const request = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
})

request.interceptors.request.use(
  config => {
    config._retryCount = config._retryCount || 0
    return config
  },
  error => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  response => {
    return response.data
  },
  async error => {
    const config = error.config || {}
    const originalUrl = config.url || 'unknown'
    
    const isConnectionError = !error.response || 
      error.code === 'ECONNABORTED' || 
      error.code === 'ECONNREFUSED' ||
      error.message?.includes('Network Error')
    
    if (isConnectionError && config._retryCount < MAX_RETRIES) {
      config._retryCount++
      console.warn(`[API 重试 ${config._retryCount}/${MAX_RETRIES}] ${originalUrl} - 连接失败，稍后重试...`)
      await sleep(RETRY_DELAY * config._retryCount)
      return request(config)
    }
    
    if (error.response) {
      console.error('响应错误:', error.response)
      switch (error.response.status) {
        case 401:
          break
        case 403:
          break
        case 404:
          break
        case 500:
          break
        default:
          break
      }
    } else if (error.request) {
      console.error(`网络错误: 无法连接到后端服务 - ${originalUrl}`)
    } else {
      console.error('请求错误:', error.message)
    }
    
    return Promise.reject(error)
  }
)

export default request
