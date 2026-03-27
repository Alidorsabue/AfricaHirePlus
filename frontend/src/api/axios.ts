import axios, { isAxiosError, type InternalAxiosRequestConfig } from 'axios'
import { getApiBaseUrl } from './env'
import { logApiFailure } from './apiDebug'

type InternalAxiosRequestConfigWithRetry = InternalAxiosRequestConfig & { _retry?: boolean }

export const api = axios.create({
  baseURL: getApiBaseUrl(),
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  // FormData : laisser axios définir Content-Type (multipart/form-data + boundary)
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err: unknown) => {
    if (!isAxiosError(err)) {
      return Promise.reject(err)
    }
    logApiFailure('axios', err)
    const original = err.config as InternalAxiosRequestConfigWithRetry | undefined
    if (!original) {
      return Promise.reject(err)
    }
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = localStorage.getItem('refresh')
      if (refresh) {
        try {
          const { data } = await axios.post<{ access: string }>(
            `${getApiBaseUrl()}/auth/token/refresh/`,
            { refresh }
          )
          localStorage.setItem('access', data.access)
          original.headers.Authorization = `Bearer ${data.access}`
          return api(original)
        } catch {
          localStorage.removeItem('access')
          localStorage.removeItem('refresh')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(err)
  }
)
