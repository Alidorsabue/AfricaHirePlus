/**
 * API client pour le rôle "Correcteur" (P8).
 *
 * Le correcteur n'a PAS de compte plateforme. Il s'authentifie via un token
 * unique reçu par email (link magique du type `/correct?token=XYZ`).
 *
 * Le token est :
 *  - stocké en sessionStorage (volatile : pas localStorage),
 *  - envoyé sur chaque requête via le header `X-Corrector-Token`,
 *  - jamais mélangé avec le JWT recruteur/candidat.
 *
 * On utilise une instance axios DÉDIÉE pour ne pas hériter de l'intercepteur
 * JWT (qui ferait un refresh vers `/auth/token/refresh/` et casserait le flux).
 */
import axios, { type AxiosInstance } from 'axios'
import { getApiBaseUrl } from './env'

// ---------------------------------------------------------------------------
// Types renvoyés par les endpoints correcteur (alignés sur les serializers)
// ---------------------------------------------------------------------------
export interface CorrectorTestInfo {
  id: number
  title: string
  description: string | null
  test_type: string
  duration_minutes: number | null
  total_score: string | number | null
  passing_score: string | number | null
  job_role: string
}

export interface CorrectorAuthCheckResponse {
  corrector: {
    email: string
    full_name: string | null
    expires_at: string | null
    scope: 'all_candidates' | 'restricted'
    assigned_count: number | null
  }
  test: CorrectorTestInfo
  sessions_to_review: number
}

export interface CorrectorSessionListItem {
  id: number
  display_code: string
  status: 'IN_PROGRESS' | 'COMPLETED' | 'EXPIRED' | string
  score: string | number | null
  max_score: string | number | null
  pending_review_points: string | number | null
  is_passed: boolean | null
  is_flagged: boolean
  submitted_at: string | null
  pending_answers_count: number
}

export interface CorrectorAnswer {
  id: number
  question_id: number
  question_text: string
  question_type: string
  question_points: number
  question_options: Array<{ label: string; correct?: boolean }> | null
  question_correct_answer: unknown
  question_section_title: string
  question_competencies: string[] | null
  /** Réponse brute du candidat (JSON variable selon question_type) */
  response: unknown
  score_obtained: string | number | null
  is_correct: boolean | null
  pending_manual_review: boolean
  file_url: string | null
  created_at: string
  updated_at: string
}

export interface CorrectorSessionDetail {
  id: number
  display_code: string
  status: string
  score: string | number | null
  max_score: string | number | null
  pending_review_points: string | number | null
  is_passed: boolean | null
  is_flagged: boolean
  tab_switch_count: number
  started_at: string | null
  submitted_at: string | null
  test_info: CorrectorTestInfo
  answers: CorrectorAnswer[]
}

export interface CorrectorReviewPayload {
  /** Note attribuée. Bornée [0 ; question.points] côté backend. */
  score: number
  /** Optionnel : forcer le statut "correct" (sinon déduit du score). */
  is_correct?: boolean | null
  /** Raison / commentaire — toujours archivé dans l'audit log. */
  reason?: string
}

export interface CorrectorReviewResponse {
  answer_id: number
  score_obtained: number
  is_correct: boolean | null
  pending_manual_review: boolean
  /** Mise à jour du score agrégé de la session après réévaluation. */
  session_score: number
  session_pending_review_points: number
  session_is_passed: boolean | null
}

// ---------------------------------------------------------------------------
// Stockage volatile du token (sessionStorage : disparaît à la fermeture onglet)
// ---------------------------------------------------------------------------
const TOKEN_KEY = 'ahp_corrector_token'

export function getCorrectorToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setCorrectorToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token)
  } catch {
    /* mode privé navigateur — on retombe sur le query param à chaque requête */
  }
}

export function clearCorrectorToken(): void {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* ignore */
  }
}

// ---------------------------------------------------------------------------
// Axios dédié — pas d'intercepteur JWT, on injecte X-Corrector-Token
// ---------------------------------------------------------------------------
const correctorAxios: AxiosInstance = axios.create({
  baseURL: getApiBaseUrl(),
  headers: { 'Content-Type': 'application/json' },
})

correctorAxios.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl()
  const token = getCorrectorToken()
  if (token) {
    config.headers['X-Corrector-Token'] = token
  }
  return config
})

// ---------------------------------------------------------------------------
// API publique du module correcteur
// ---------------------------------------------------------------------------
export const correctorsApi = {
  /**
   * Valide un token et récupère le contexte (test, scope, expiration).
   * Utilisé à l'arrivée sur `/correct?token=...`.
   *
   * NB : l'endpoint backend est un POST (CSRF non requis car
   * `authentication_classes = []` et le token sert d'authentifiant).
   */
  authCheck: () =>
    correctorAxios.post<CorrectorAuthCheckResponse>('/tests/correctors/auth/check/'),

  /** Liste des sessions visibles par le correcteur (anonymisées). */
  listSessions: () =>
    correctorAxios.get<CorrectorSessionListItem[]>('/tests/correctors/sessions/'),

  /** Détail anonymisé d'une session (questions + réponses du candidat). */
  getSession: (sessionId: number) =>
    correctorAxios.get<CorrectorSessionDetail>(`/tests/correctors/sessions/${sessionId}/`),

  /**
   * Override / correction manuelle d'une réponse (toute typologie, y compris
   * questions auto-corrigées). Borné [0 ; question.points] côté backend.
   */
  reviewAnswer: (answerId: number, payload: CorrectorReviewPayload) =>
    correctorAxios.post<CorrectorReviewResponse>(
      `/tests/correctors/answers/${answerId}/review/`,
      payload,
    ),
}
