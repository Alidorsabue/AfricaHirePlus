import { api } from './axios'
import type { Application, AtsBreakdown, CandidateProfile } from '../types'

/** Réponse GET ma candidature pour une offre (pré-remplir formulaire). */
export interface MyApplicationByJobResponse {
  application: {
    id: number
    status: string
    cover_letter: string
    applied_at: string
    cover_letter_document_url?: string | null
  }
  candidate: CandidateProfile
  job_still_open: boolean
}

/** Payload pour postuler (endpoint public). */
export interface PublicApplyPayload {
  job_offer_slug: string
  email: string
  first_name: string
  last_name: string
  cover_letter?: string
  phone?: string
  linkedin_url?: string
  portfolio_url?: string
  summary?: string
  experience_years?: number | null
  education_level?: string
  current_position?: string
  location?: string
  country?: string
  skills?: string[]
}

export const applicationsApi = {
  list: (params?: { status?: string; job_offer?: number; with_cv?: boolean }) =>
    api.get<Application[]>('/applications/', {
      params: params
        ? { status: params.status, job_offer: params.job_offer, ...(params.with_cv ? { with_cv: 1 } : {}) }
        : undefined,
    }),
  /** Candidatures du candidat connecté (rôle candidat). */
  mine: () => api.get<Application[] | { results: Application[] }>('/applications/mine/'),
  /** Ma candidature pour une offre (par slug ou id) — pour pré-remplir le formulaire. 404 si aucune. */
  getMyApplicationByJob: (params: { job_offer_slug?: string; job_offer_id?: number }) =>
    api.get<MyApplicationByJobResponse>('/applications/my-application/', { params }),
  get: (id: number) => api.get<Application>(`/applications/${id}/`),
  /** Détail du calcul ATS pour l’onglet Analyse CV (chargé à la demande). */
  getAtsBreakdown: (id: number) =>
    api.get<AtsBreakdown>(`/applications/${id}/ats-breakdown/`).then((r) => r.data),
  update: (id: number, data: Partial<Application>) =>
    api.patch<Application>(`/applications/${id}/`, data),
  updateStatus: (id: number, status: string) =>
    api.patch(`/applications/${id}/status/`, { status }),
  exportExcel: () =>
    api.get('/applications/export/xlsx/', { responseType: 'blob' }),
  exportShortlistedExcel: () =>
    api.get('/applications/export/shortlisted/xlsx/', { responseType: 'blob' }),
  /** Override manuel : ADD_TO_SHORTLIST, REMOVE_FROM_SHORTLIST, FORCE_STATUS, UPDATE_SCORE. */
  manualOverride: (
    id: number,
    payload: {
      action: 'ADD_TO_SHORTLIST' | 'REMOVE_FROM_SHORTLIST' | 'FORCE_STATUS' | 'UPDATE_SCORE'
      reason?: string
      new_status?: string
      new_score?: number
    }
  ) => api.post<Application>(`/applications/${id}/manual-override/`, payload),
  /** Postuler à une offre (sans auth). Envoyer FormData si CV joint. Timeout long pour upload de fichiers. */
  publicApply: (data: PublicApplyPayload | FormData) =>
    api.post<{ message: string; application_id: number; status: string; screening_score: string | null }>(
      '/applications/public/apply/',
      data,
      { timeout: 90_000 }
    ),
}
