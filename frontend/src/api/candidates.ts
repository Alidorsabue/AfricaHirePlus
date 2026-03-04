import { api } from './axios'
import type { Candidate, CandidateProfile } from '../types'

export const candidatesApi = {
  list: (params?: { country?: string; experience_years?: number }) =>
    api.get<Candidate[]>('/candidates/', { params }),
  get: (id: number) => api.get<Candidate>(`/candidates/${id}/`),
  update: (id: number, data: Partial<Candidate>) =>
    api.patch<Candidate>(`/candidates/${id}/`, data),
  exportExcel: () =>
    api.get('/candidates/export/xlsx/', { responseType: 'blob' }),
  /** Profil du candidat connecté. Si companyId fourni, retourne le profil pour cette entreprise (pré-remplir formulaire). */
  me: (companyId?: number) =>
    api.get<CandidateProfile>('/candidates/me/', companyId != null ? { params: { company: companyId } } : undefined),
  updateMe: (data: Partial<CandidateProfile>) =>
    api.patch<CandidateProfile>('/candidates/me/', data),
}
