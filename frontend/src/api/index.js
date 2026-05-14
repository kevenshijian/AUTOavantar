import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

apiClient.interceptors.request.use(
  config => {
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`)
    return config
  },
  error => {
    console.error('[API Request Error]', error)
    return Promise.reject(error)
  }
)

apiClient.interceptors.response.use(
  response => {
    console.log(`[API Response] ${response.status} ${response.config.url}`)
    return response.data
  },
  error => {
    console.error('[API Response Error]', error.response || error)
    
    const errorMessage = error.response?.data?.detail || error.message || '网络错误'
    
    return Promise.reject(new Error(errorMessage))
  }
)

export default apiClient
