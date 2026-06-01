import { api } from './axios'
import type { Candidate, CandidateProfile } from '../types'

export const candidatesApi = {
  list: (params?: { country?: string; experience_years?: number }) =>
    api.get<Candidate[]>('/candidates/', { params }),
  get: (id: number) => api.get<Candidate>(`/candidates/${id}/`),
  update: (id: number, data: Partial<Candidate>) =>
    api.patch<Candidate>(`/candidates/${id}/`, data),
  /** P10: tags (recruteur). */
  updateTags: (id: number, tags: string[]) =>
    api.patch<{ id: number; tags: string[] }>(`/candidates/${id}/tags/`, { tags }),
  /** P10: anonymisation RGPD (recruteur). */
  anonymize: (id: number) =>
    api.post<{ message: string; id: number; is_anonymized: boolean; anonymized_at: string | null }>(
      `/candidates/${id}/anonymize/`
    ),
  exportExcel: () =>
    api.get('/candidates/export/xlsx/', { responseType: 'blob' }),
  /** Profil du candidat connecté. Si companyId fourni, retourne le profil pour cette entreprise (pré-remplir formulaire). */
  me: (companyId?: number) =>
    api.get<CandidateProfile>('/candidates/me/', companyId != null ? { params: { company: companyId } } : undefined),
  updateMe: (data: Partial<CandidateProfile>) =>
    api.patch<CandidateProfile>('/candidates/me/', data),
  /** P10: RGPD portabilité (candidat). */
  exportMe: () =>
    api.get('/candidates/me/export/', { responseType: 'blob' }),
  /** P10: RGPD effacement (candidat). */
  deleteMe: () =>
    api.delete<{ message: string; anonymized_ids: number[] }>('/candidates/me/'),
}
