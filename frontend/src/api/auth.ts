import { api } from './axios'
import type { User } from '../types'

export const authApi = {
  login: (username: string, password: string) =>
    api.post<{ access: string; refresh: string }>('/auth/token/', { username, password }),

  refresh: (refresh: string) =>
    api.post<{ access: string }>('/auth/token/refresh/', { refresh }),

  me: () => api.get<User>('/auth/me/'),

  updateMe: (
    data:
      | Partial<Pick<User, 'username' | 'email' | 'first_name' | 'last_name' | 'phone'>>
      | FormData
  ) => api.patch<User>('/auth/me/', data),

  changePassword: (data: {
    current_password: string
    new_password: string
    new_password_confirm: string
  }) => api.post<{ message: string }>('/auth/change-password/', data),

  registerCompany: (data: {
    company_name: string
    company_slug?: string
    company_website?: string
    company_email?: string
    company_country?: string
    email: string
    username: string
    password: string
    password_confirm: string
    first_name?: string
    last_name?: string
    phone?: string
  }) => api.post('/auth/register/company/', data),

  registerCandidate: (data: {
    email: string
    password: string
    password_confirm: string
    first_name: string
    last_name: string
    phone?: string
  }) => api.post<{ user: User; message: string }>('/auth/register/candidate/', data),
}
