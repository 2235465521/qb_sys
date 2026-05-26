// Axios 实例 + JWT 拦截器
import axios from 'axios'
import { message } from 'antd'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截：自动附加 JWT Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status

    if (status === 401) {
      // 防止死循环：登录页或登录接口不重定向
      if (window.location.pathname === '/login' || error.config.url?.includes('/auth/login')) {
        return Promise.reject(error)
      }

      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const res = await axios.post('/api/auth/refresh/', { refresh })
          const newAccess = res.data.access
          localStorage.setItem('access_token', newAccess)
          error.config.headers['Authorization'] = `Bearer ${newAccess}`
          return apiClient.request(error.config)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      } else {
        localStorage.clear()
        window.location.href = '/login'
      }
    } else if (status === 403) {
      message.error('权限不足')
    } else if (status === 500) {
      message.error('服务器错误，请联系管理员')
    }

    return Promise.reject(error)
  }
)

export default apiClient
