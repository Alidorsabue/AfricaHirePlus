export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  role: string
  company: number | null
  phone: string
  avatar: string | null
  is_active: boolean
  date_joined: string
}

export interface TokenResponse {
  access: string
  refresh: string
}

export interface Company {
  id: number
  name: string
  slug: string
  logo?: string | null
  website?: string
  description?: string
  email?: string
  phone?: string
  address?: string
  city?: string
  country?: string
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export type SelectionMode = 'auto' | 'semi_automatic'

export interface JobOffer {
  id: number
  company: number
  title: string
  slug: string
  description: string
  description_document?: string | null
  description_document_url?: string | null
  requirements: string
  benefits: string
  location: string
  country: string
  contract_type: string
  status: string
  salary_min: number | null
  salary_max: number | null
  salary_currency: string
  salary_visible: boolean
  deadline: string | null
  published_at: string | null
  closed_at: string | null
  created_by: number | null
  screening_rules: ScreeningRule[]
  selection_mode?: SelectionMode
  preselection_settings?: {
    score_threshold: number
    max_candidates: number | null
  }
  selection_settings?: {
    score_threshold: number
    max_candidates: number | null
    selection_mode: SelectionMode
    selection_rules?: ScreeningRule[]
  }
  /** Critères identifiés à partir de l'offre (exigences en priorité) : mots-clés, expérience, éducation */
  suggested_criteria?: {
    keywords?: string[]
    min_experience?: number | null
    education_level?: string | null
  }
  created_at: string
  updated_at: string
}

export interface ScreeningRule {
  id?: number
  rule_type: 'keywords' | 'min_experience' | 'education_level' | 'location' | 'custom'
  value: Record<string, unknown>
  weight: number | string
  is_required: boolean
  order: number
}

export interface Candidate {
  id: number
  company?: number
  email: string
  first_name: string
  last_name: string
  phone?: string
  resume?: string | null
  raw_cv_text?: string
  linkedin_url?: string
  portfolio_url?: string
  summary?: string
  experience_years?: number | null
  education_level?: string
  current_position?: string
  location?: string
  country?: string
  skills?: string[]
  created_at?: string
  updated_at?: string
}

/** Profil candidat complet (GET/PATCH /candidates/me/) pour pré-remplissage formulaire et page Mon profil */
export interface CandidateProfile extends Candidate {
  title?: string
  preferred_name?: string
  date_of_birth?: string | null
  gender?: string
  address?: string
  address_line2?: string
  city?: string
  postcode?: string
  cell_number?: string
  nationality?: string
  second_nationality?: string
  resume_url?: string | null
  education?: Array<Record<string, string>>
  experience?: Array<Record<string, string>>
  languages?: Array<Record<string, string>>
  references?: Array<Record<string, string>>
}

export type ApplicationStatus =
  | 'applied'
  | 'preselected'
  | 'rejected_preselection'
  | 'shortlisted'
  | 'rejected_selection'
  | 'interview'
  | 'offer'
  | 'hired'
  | 'rejected'
  | 'withdrawn'

/** Détail d’un critère de score (présélection pondérée). */
export interface PreselectionScoreDetail {
  criterion?: string
  passed?: boolean
  weight_awarded?: number
}

/** Détail par catégorie (analyse approfondie). */
export interface CategoryBreakdown {
  keywords_found?: string[]
  keywords_missing?: string[]
  score?: number
  required?: string | string[] | null
  candidate?: string | number | null
  match?: boolean | null
  required_years?: number | null
  candidate_years?: number | null
}

/** Détail du calcul ATS (mots-clés + sémantique) pour l'onglet Analyse CV. */
export interface AtsBreakdown {
  categories?: {
    mots_cles?: CategoryBreakdown
    niveau_etudes?: CategoryBreakdown
    experience?: CategoryBreakdown
    langue?: CategoryBreakdown
    competences?: CategoryBreakdown
    localisation?: CategoryBreakdown
    personnalise?: CategoryBreakdown
  }
  keyword_score?: number
  semantic_score?: number
  total_score?: number
  keywords_from_job?: string[]
  keywords_found?: string[]
  keywords_missing?: string[]
}

export interface Application {
  id: number
  job_offer: JobOffer | number
  candidate: Candidate | number
  status: ApplicationStatus
  cover_letter: string
  cover_letter_document_url?: string | null
  source: string
  screening_score: string | null
  preselection_score?: number | null
  selection_score?: number | null
  preselection_score_details?: PreselectionScoreDetail[] | null
  ats_breakdown?: AtsBreakdown | null
  selection_score_details?: unknown
  is_manually_adjusted?: boolean
  manual_override_reason?: string | null
  manually_added_to_shortlist?: boolean
  notes: string
  applied_at: string
  created_at: string
  updated_at: string
}

/** Entrée leaderboard (onglet Présélection) : rang, candidat, score, statut, badge Auto/Manuel */
export interface LeaderboardEntry {
  id: number
  rank: number
  candidate: Candidate
  preselection_score: number | null
  status: string
  badge: 'automatic' | 'manual'
  created_at: string
}

/** Résultat simulation shortlist (sans modification en base) */
export interface ShortlistSimulationEntry {
  application_id: number
  candidate_id: number
  candidate_name: string
  preselection_score: number | null
  selection_score: number
  rank: number
}

export interface ShortlistSimulationResult {
  shortlist: ShortlistSimulationEntry[]
}

/** Entrée shortlist générée (après generate-shortlist) */
export interface ShortlistEntry {
  id: number
  candidate: Candidate
  preselection_score: number | null
  selection_score: number | null
  status: string
}

/** KPI dashboard offre */
export interface JobKpi {
  total_applications: number
  total_preselected: number
  total_shortlisted: number
  rejection_rate_preselection: number
  rejection_rate_selection: number
  average_preselection_score: number | null
  average_selection_score: number | null
  highest_score: number | null
  lowest_score: number | null
}

export interface TestSection {
  id: number
  title: string
  order: number
}

export interface Test {
  id: number
  company: number
  job_offer?: number | { id: number; title: string }
  title: string
  description: string
  test_type: string
  duration_minutes: number | null
  passing_score: string | null
  access_code?: string | null
  is_active: boolean
  sections?: TestSection[]
  questions: Question[]
  created_at: string
  updated_at: string
}

export interface Question {
  id: number
  section?: number | null
  section_title?: string | null
  question_type: string
  text: string
  options: Array<{ id: string; label: string; correct?: boolean }>
  correct_answer: string | string[] | number | null
  points: number
  order: number
  attachment?: string | null
  code_language?: string | null
  starter_code?: string | null
}

export interface CandidateTestResult {
  id: number
  application: number
  test: number
  status: string
  score: string | number | null
  max_score: string | number | null
  answers: Record<string, unknown>
  started_at: string | null
  submitted_at: string | null
  tab_switch_count?: number
  is_flagged?: boolean
  created_at: string
  updated_at: string
}

export interface EmailTemplate {
  id: number
  company: number
  name: string
  template_type: string
  subject: string
  body_html: string
  body_text: string
  is_active: boolean
  created_at: string
  updated_at: string
}
