import { api } from './axios'
import type {
  JobOffer,
  JobKpi,
  LeaderboardEntry,
  ShortlistEntry,
  ShortlistSimulationResult,
} from '../types'

/** Offre telle que renvoyée par l’API publique (sans company, sans infos sensibles). */
export interface PublicJobOffer {
  id: number
  company: number
  title: string
  slug: string
  description: string
  description_document_url: string | null
  requirements: string
  benefits: string
  location: string
  country: string
  contract_type: string
  salary_min: number | null
  salary_max: number | null
  salary_currency: string
  salary_visible: boolean
  published_at: string | null
  deadline: string | null
  created_at: string
}

export const jobsApi = {
  list: (params?: { status?: string }) => api.get<JobOffer[]>('/jobs/', { params }),
  get: (id: number) => api.get<JobOffer>(`/jobs/${id}/`),
  /** Liste des offres publiées (accès public). */
  listPublic: () =>
    api.get<PublicJobOffer[] | { results: PublicJobOffer[] }>('/jobs/public/'),
  /** Offre publique par slug (pour la page candidats, sans auth). */
  getPublicBySlug: (slug: string) =>
    api.get<PublicJobOffer>(`/jobs/public/${encodeURIComponent(slug)}/`),
  create: (data: Partial<JobOffer> | FormData) =>
    api.post<JobOffer>('/jobs/', data),
  update: (id: number, data: Partial<JobOffer> | FormData) =>
    api.patch<JobOffer>(`/jobs/${id}/`, data),
  close: (id: number) =>
    api.post<{ message: string; job: JobOffer }>(`/jobs/${id}/close/`),
  /** Recalcule les scores de présélection pour toutes les candidatures de l'offre (ATS JD vs CV). */
  refreshScores: (jobId: number) =>
    api.post<{ message: string; updated_count: number }>(`/jobs/${jobId}/refresh-scores/`),
  getLeaderboard: (jobId: number) =>
    api.get<LeaderboardEntry[]>(`/jobs/${jobId}/leaderboard/`),
  simulateShortlist: (
    jobId: number,
    params: { threshold: number; max_candidates?: number }
  ) =>
    api.post<ShortlistSimulationResult>(`/jobs/${jobId}/simulate-shortlist/`, params),
  generateShortlist: (jobId: number) =>
    api.post<{ message: string; shortlist: ShortlistEntry[] }>(
      `/jobs/${jobId}/generate-shortlist/`
    ),
  getKpi: (jobId: number) => api.get<JobKpi>(`/jobs/${jobId}/kpi/`),
  exportShortlistPdf: (jobId: number) =>
    api.get(`/jobs/${jobId}/export-shortlist/`, { responseType: 'blob' }),
  exportExcel: () =>
    api.get('/jobs/export/xlsx/', { responseType: 'blob' }),
}
