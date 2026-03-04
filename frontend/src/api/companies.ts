import { api } from './axios'
import type { Company } from '../types'

export const companiesApi = {
  list: () => api.get<Company[]>('/companies/'),
  get: (id: number) => api.get<Company>(`/companies/${id}/`),
  update: (id: number, data: Partial<Company> | FormData) =>
    api.patch<Company>(`/companies/${id}/`, data),
}
