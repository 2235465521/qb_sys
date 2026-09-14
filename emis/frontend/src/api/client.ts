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

let isRefreshing = false
let failedQueue: Array<{
  resolve: (value?: unknown) => void
  reject: (reason?: unknown) => void
}> = []

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// 响应拦截：统一错误处理与并发安全的 JWT 无感刷新
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const status = error.response?.status

    if (status === 401 && originalRequest) {
      // 防止死循环：登录页或登录接口不重定向
      if (window.location.pathname === '/login' || originalRequest.url?.includes('/auth/login')) {
        return Promise.reject(error)
      }

      if (originalRequest._retry) {
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            if (originalRequest.headers.set) {
              originalRequest.headers.set('Authorization', `Bearer ${token}`)
            } else {
              originalRequest.headers['Authorization'] = `Bearer ${token}`
            }
            return apiClient.request(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const res = await axios.post('/api/auth/refresh/', { refresh })
          const newAccess = res.data.access
          localStorage.setItem('access_token', newAccess)

          if (originalRequest.headers.set) {
            originalRequest.headers.set('Authorization', `Bearer ${newAccess}`)
          } else {
            originalRequest.headers['Authorization'] = `Bearer ${newAccess}`
          }

          processQueue(null, newAccess)
          return apiClient.request(originalRequest)
        } catch (refreshErr) {
          processQueue(refreshErr, null)
          localStorage.clear()
          window.location.href = '/login'
          return Promise.reject(refreshErr)
        } finally {
          isRefreshing = false
        }
      } else {
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(error)
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
