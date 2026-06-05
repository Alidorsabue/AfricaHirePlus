import { api } from './axios'
import type {
  Application,
  AtsBreakdown,
  CandidateProfile,
  CandidateApplication,
  ApplicationNote,
  ApplicationAuditLog,
} from '../types'

/** Données structurées retournées par l'analyse CV pour le formulaire. */
export interface CvParsedFormData {
  title?: string
  first_name?: string
  last_name?: string
  preferred_name?: string
  date_of_birth?: string | null
  gender?: string
  email?: string
  phone?: string
  cell_number?: string
  address?: string
  address_line2?: string
  city?: string
  country?: string
  postcode?: string
  nationality?: string
  second_nationality?: string
  linkedin_url?: string
  portfolio_url?: string
  summary?: string
  skills?: string[] | string
  experience_years?: number | null
  education_level?: string
  current_position?: string
  location?: string
  education?: Array<Record<string, string>>
  experience?: Array<Record<string, string>>
  languages?: Array<Record<string, string>>
  references?: Array<Record<string, string>>
}

/** Score de confiance 0–1 par rubrique du formulaire (clé = FORM_SECTIONS). */
export type CvSectionConfidence = Partial<Record<
  'personalDetails' | 'education' | 'experience' | 'skills' | 'languages' | 'references' | 'documents',
  number
>>

export interface ParseCvResponse {
  source: 'upload' | 'last_application'
  form_data: CvParsedFormData
  section_confidence?: CvSectionConfidence
  resume_url?: string | null
  resume_filename?: string | null
  warnings?: string[]
}

export interface LastCvInfoResponse {
  available: boolean
  resume_url?: string | null
  resume_filename?: string | null
  applied_at?: string
  job_title?: string | null
  application_id?: number
}

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
  mine: () => api.get<CandidateApplication[] | { results: CandidateApplication[] }>('/applications/mine/'),
  /** Ma candidature pour une offre (par slug ou id) — pour pré-remplir le formulaire. 404 si aucune. */
  getMyApplicationByJob: (params: { job_offer_slug?: string; job_offer_id?: number }) =>
    api.get<MyApplicationByJobResponse>('/applications/my-application/', { params }),
  get: (id: number) => api.get<Application>(`/applications/${id}/`),
  /** Détail du calcul ATS pour l’onglet Analyse CV (chargé à la demande). */
  getAtsBreakdown: (id: number) =>
    api.get<AtsBreakdown>(`/applications/${id}/ats-breakdown/`).then((r) => r.data),
  update: (id: number, data: Partial<Application>) =>
    api.patch<Application>(`/applications/${id}/`, data),
  updateStatus: (id: number, status: string, reason?: string) =>
    api.patch(`/applications/${id}/status/`, { status, ...(reason ? { reason } : {}) }),
  /** P10: retrait candidature (candidat). */
  withdraw: (id: number, reason?: string) =>
    api.post<{ message: string; application_id: number; status: string }>(
      `/applications/${id}/withdraw/`,
      reason ? { reason } : undefined
    ),
  /** P10: bulk status (recruteur). */
  bulkStatus: (payload: { application_ids: number[]; status: string; reason?: string }) =>
    api.post<{ updated: number[]; errors: Array<{ id: number; detail: string }> }>(
      '/applications/bulk-status/',
      payload
    ),
  /** P10: notes internes (recruteur). */
  notes: {
    list: (applicationId: number) =>
      api.get<ApplicationNote[] | { results: ApplicationNote[] }>(`/applications/${applicationId}/notes/`),
    create: (applicationId: number, payload: { body: string; is_pinned?: boolean }) =>
      api.post<ApplicationNote>(`/applications/${applicationId}/notes/`, payload),
    update: (noteId: number, payload: Partial<Pick<ApplicationNote, 'body' | 'is_pinned'>>) =>
      api.patch<ApplicationNote>(`/applications/notes/${noteId}/`, payload),
    delete: (noteId: number) =>
      api.delete(`/applications/notes/${noteId}/`),
  },
  /** P10: audit log (recruteur). */
  audit: {
    list: (applicationId: number) =>
      api.get<ApplicationAuditLog[] | { results: ApplicationAuditLog[] }>(`/applications/${applicationId}/audit/`),
  },
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
  /** Infos sur le dernier CV déposé (candidature précédente). */
  getLastCvInfo: (params?: { exclude_job_slug?: string }) =>
    api.get<LastCvInfoResponse>('/applications/last-cv-info/', { params }),
  /** Analyse un CV uploadé et retourne les champs pour pré-remplir le formulaire. */
  parseCv: (file: File) => {
    const fd = new FormData()
    fd.append('resume', file)
    return api.post<ParseCvResponse>('/applications/parse-cv/', fd, {
      timeout: 90_000,
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  /** Réutilise le CV de la dernière candidature pour pré-remplir le formulaire. */
  parseLastCv: (params?: { exclude_job_slug?: string }) => {
    const fd = new FormData()
    fd.append('use_last_cv', 'true')
    if (params?.exclude_job_slug) fd.append('exclude_job_slug', params.exclude_job_slug)
    return api.post<ParseCvResponse>('/applications/parse-cv/', fd, { timeout: 60_000 })
  },
}
