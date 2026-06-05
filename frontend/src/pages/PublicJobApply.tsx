/**
 * Page de candidature à une offre (route /offres/:slug/postuler).
 * Formulaire multi-sections : identité, CV, formation, expérience, langues, références, lettre de motivation.
 * Connexion optionnelle : si connecté (candidat), les champs sont pré-remplis et la candidature est liée au profil.
 */
import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { ArrowLeft, FileUp, Send, Sparkles } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { jobsApi } from '../api/jobs'
import {
  applicationsApi,
  type CvParsedFormData,
  type CvSectionConfidence,
  type ParseCvResponse,
} from '../api/applications'
import { candidatesApi } from '../api/candidates'
import type { CandidateProfile } from '../types'

/** Extrait un message d'erreur lisible depuis une erreur API (axios ou Error). */
function getApiErrorMessage(error: unknown): string {
  if (isAxiosError(error) && error.response?.data != null) {
    const d = error.response.data
    if (typeof d === 'string') return d
    if (typeof d === 'object' && !Array.isArray(d)) {
      const format = (v: unknown): string => {
        if (v == null) return ''
        if (typeof v === 'string') return v
        if (Array.isArray(v)) return v.map(format).join(', ')
        if (typeof v === 'object') return JSON.stringify(v)
        return String(v)
      }
      const parts = Object.entries(d).map(([k, v]) => `${k}: ${format(v)}`)
      return parts.join(' — ')
    }
  }
  return error instanceof Error ? error.message : String(error)
}

// ——— Types et constantes pour formation, expérience, langues, références ———

export type EducationEntry = {
  education_type: string
  degree_type: string
  discipline: string
  other_specializations: string
  country: string
  institution: string
  city_campus: string
  study_level: string
  enrollment_status: string
  start_year: string
  end_year: string
}
const emptyEdu = (): EducationEntry => ({
  education_type: '',
  degree_type: '',
  discipline: '',
  other_specializations: '',
  country: '',
  institution: '',
  city_campus: '',
  study_level: '',
  enrollment_status: '',
  start_year: '',
  end_year: '',
})
const EDUCATION_TYPES = ['university_graduate', 'bts_dut', 'baccalaureat', 'high_school', 'other'] as const
const DEGREE_TYPES = ['master', 'licence', 'doctorate', 'bachelor', 'other'] as const
const DISCIPLINES = ['computer_science', 'civil_engineering', 'commerce', 'medicine', 'law', 'other'] as const
const STUDY_LEVELS = ['completed', 'in_progress', 'abandoned'] as const
const ENROLLMENT_STATUSES = ['full_time', 'part_time'] as const
export type ExperienceEntry = {
  employment_status: string
  employment_type: string
  employment_type_details: string
  job_title: string
  job_contract_type: string
  job_level: string
  responsibilities: string
  start_month: string
  start_year: string
  start_day: string
  end_month: string
  end_year: string
  end_day: string
  company_name: string
  company_sector: string
  country: string
  city: string
  department: string
  manager_name: string
}
const emptyExp = (): ExperienceEntry => ({
  employment_status: '',
  employment_type: '',
  employment_type_details: '',
  job_title: '',
  job_contract_type: '',
  job_level: '',
  responsibilities: '',
  start_month: '',
  start_year: '',
  start_day: '',
  end_month: '',
  end_year: '',
  end_day: '',
  company_name: '',
  company_sector: '',
  country: '',
  city: '',
  department: '',
  manager_name: '',
})
const EMPLOYMENT_STATUSES = ['currently_employed', 'not_employed', 'student', 'other'] as const
const EMPLOYMENT_TYPES = ['full_time', 'part_time', 'contract', 'internship', 'other'] as const
const EMPLOYMENT_TYPE_DETAILS = ['public_sector', 'private_sector', 'ngo', 'international', 'other'] as const
const JOB_CONTRACT_TYPES = ['permanent', 'fixed_term', 'freelance', 'internship', 'other'] as const
const JOB_LEVELS = ['not_available', 'entry', 'mid', 'senior', 'manager', 'executive'] as const
const COMPANY_SECTORS = ['human_resources', 'it', 'finance', 'health', 'education', 'other'] as const
export type LanguageEntry = {
  language: string
  speaking_proficiency: string
  reading_proficiency: string
  writing_proficiency: string
}
const emptyLang = (): LanguageEntry => ({
  language: '',
  speaking_proficiency: '',
  reading_proficiency: '',
  writing_proficiency: '',
})
const LANGUAGES_LIST = ['french', 'english', 'swahili', 'lingala', 'arabic', 'spanish', 'portuguese', 'other'] as const
const PROFICIENCY_LEVELS = ['fluent', 'proficient', 'intermediate', 'basic', 'elementary'] as const
export type ReferenceEntry = {
  first_name: string
  last_name: string
  organization: string
  job_title: string
  phone: string
  email: string
}
const emptyRef = (): ReferenceEntry => ({
  first_name: '',
  last_name: '',
  organization: '',
  job_title: '',
  phone: '',
  email: '',
})

const TITLES = ['Mr', 'Mrs', 'Ms', 'Dr', 'Other'] as const
const GENDERS = ['Male', 'Female', 'Other'] as const
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const DAYS = Array.from({ length: 31 }, (_, i) => String(i + 1))
const YEARS = Array.from({ length: 80 }, (_, i) => String(new Date().getFullYear() - 18 - i))

type CvAutofillSectionKey =
  | 'personalDetails'
  | 'education'
  | 'experience'
  | 'skills'
  | 'languages'
  | 'references'
  | 'documents'

function confidenceBadge(
  score: number | undefined,
  t: (key: string) => string
): { label: string; cls: string } | null {
  if (score == null || score <= 0) return null
  if (score >= 0.75) {
    return {
      label: t('publicJob.cvConfidenceHigh'),
      cls: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
    }
  }
  if (score >= 0.45) {
    return {
      label: t('publicJob.cvConfidenceMedium'),
      cls: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
    }
  }
  return {
    label: t('publicJob.cvConfidenceLow'),
    cls: 'bg-slate-200 text-slate-600 dark:bg-slate-600 dark:text-slate-300',
  }
}

export default function PublicJobApply() {
  const { slug } = useParams<{ slug: string }>()
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [success, setSuccess] = useState<string | null>(null)
  const [form, setForm] = useState({
    title: '',
    first_name: '',
    last_name: '',
    preferred_name: '',
    dob_day: '',
    dob_month: '',
    dob_year: '',
    gender: '',
    email: '',
    address: '',
    address_line2: '',
    city: '',
    country: '',
    postcode: '',
    phone: '',
    cell_number: '',
    nationality: '',
    second_nationality: '',
    cover_letter: '',
    linkedin_url: '',
    portfolio_url: '',
    summary: '',
    skills: '',
    experience_years: '' as string | number,
    education_level: '',
    current_position: '',
    location: '',
    signature_text: '',
    signature_agree: false,
    allow_contact_references: '' as '' | 'yes' | 'no',
  })
  const [education, setEducation] = useState<EducationEntry[]>([emptyEdu()])
  const [experience, setExperience] = useState<ExperienceEntry[]>([emptyExp()])
  const [languages, setLanguages] = useState<LanguageEntry[]>([emptyLang()])
  const [references, setReferences] = useState<ReferenceEntry[]>([emptyRef(), emptyRef(), emptyRef()])
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [coverLetterFile, setCoverLetterFile] = useState<File | null>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [showDraftSaved, setShowDraftSaved] = useState(false)
  const [signatureError, setSignatureError] = useState<string | null>(null)
  const [cvParsing, setCvParsing] = useState(false)
  const [cvAutofillMessage, setCvAutofillMessage] = useState<string | null>(null)
  const [cvAutofillWarnings, setCvAutofillWarnings] = useState<string[]>([])
  const [cvAutofillError, setCvAutofillError] = useState<string | null>(null)
  const [cvSectionConfidence, setCvSectionConfidence] = useState<CvSectionConfidence>({})
  const [pendingCvAutofill, setPendingCvAutofill] = useState<{
    formData: CvParsedFormData
    sectionConfidence: CvSectionConfidence
    warnings: string[]
    resumeFile: File | null
    conflicts: string[]
    successMessage: string
  } | null>(null)
  const lastPreFillSourceRef = useRef<'application' | 'profile' | null>(null)
  const cvAutofillInputRef = useRef<HTMLInputElement>(null)

  const FORM_SECTIONS = [
    'personalDetails',
    'education',
    'experience',
    'skills',
    'languages',
    'references',
    'documents',
    'signature',
  ] as const
  const totalSteps = FORM_SECTIONS.length
  const isLastStep = currentStep === totalSteps - 1

  const applyUrl = slug ? `/offres/${slug}/postuler` : ''

  const { data: jobRes, isLoading, error } = useQuery({
    queryKey: ['publicJob', slug],
    queryFn: () => jobsApi.getPublicBySlug(slug!),
    enabled: !!slug && !!user,
  })

  const job = jobRes?.data
  const companyId = job?.company != null ? Number(job.company) : null
  const isExpired = Boolean(
    job?.deadline && new Date(job.deadline).getTime() < Date.now()
  )
  // Charger profil et candidature existante dès qu'on a un utilisateur et l'offre (pas seulement si role === 'candidate')
  const profileQueryEnabled = !!user && !!job
  const myApplicationQueryEnabled = !!slug && !!user && !!job
  const { data: myApplicationRes, isLoading: myApplicationLoading } = useQuery({
    queryKey: ['myApplicationByJob', slug],
    queryFn: async () => {
      try {
        const res = await applicationsApi.getMyApplicationByJob({ job_offer_slug: slug! })
        return res.data
      } catch (e: unknown) {
        if (isAxiosError(e) && e.response?.status === 404) {
          return { application: null, candidate: null, job_still_open: false }
        }
        throw e
      }
    },
    enabled: myApplicationQueryEnabled,
    retry: false,
  })
  const myApplicationData = myApplicationRes
  const { data: lastCvInfo } = useQuery({
    queryKey: ['lastCvInfo', slug],
    queryFn: () => applicationsApi.getLastCvInfo(slug ? { exclude_job_slug: slug } : undefined).then((r) => r.data),
    enabled: !!user && !!job,
    retry: false,
  })

  const { data: profileData, isLoading: profileLoading } = useQuery({
    queryKey: ['candidateProfile', 'apply', companyId ?? 'any'],
    queryFn: async ({ queryKey }) => {
      const cid = queryKey[2] as number | 'any' | null | undefined
      const id = (cid === 'any' || cid == null) ? undefined : cid
      try {
        const res = await candidatesApi.me(id)
        return res.data
      } catch (e: unknown) {
        if (isAxiosError(e)) {
          const status = e.response?.status
          if (status === 404 || status === 403) {
            if (id != null) {
              try {
                const fallback = await candidatesApi.me()
                return fallback.data
              } catch {
                return null
              }
            }
            return null
          }
        }
        throw e
      }
    },
    enabled: profileQueryEnabled,
    retry: false,
  })

  // Pré-remplir depuis la candidature existante pour cette offre (priorité) ou depuis le profil candidat
  useEffect(() => {
    if (!user) return
    const fromApplication = myApplicationData?.candidate && typeof myApplicationData.candidate === 'object'
      ? myApplicationData.candidate
      : null
    const fromProfile = profileData as CandidateProfile | null | undefined
    const profile = fromApplication ?? (fromProfile && typeof fromProfile === 'object' ? fromProfile : null)
    if (!profile) {
      if (fromProfile === undefined && !fromApplication) return
      setForm((p) => ({
        ...p,
        email: user?.email || p.email,
        first_name: user?.first_name || p.first_name,
        last_name: user?.last_name || p.last_name,
      }))
      return
    }
    const source = fromApplication ? 'application' : 'profile'
    lastPreFillSourceRef.current = source
    const dob = profile.date_of_birth
    let dob_day = ''
    let dob_month = ''
    let dob_year = ''
    if (dob && /^\d{4}-\d{2}-\d{2}$/.test(dob)) {
      const [y, m, d] = dob.split('-')
      dob_year = y
      dob_day = String(Number(d))
      const monthNum = Number(m)
      if (monthNum >= 1 && monthNum <= 12) dob_month = MONTHS[monthNum - 1]
    }
    const skillsRaw = (profile as any).skills
    const skillsArray = Array.isArray(skillsRaw)
      ? skillsRaw
      : typeof skillsRaw === 'string'
        ? skillsRaw.split(/[,;\n]/).map((s: string) => s.trim()).filter((s: string) => s.length > 0)
        : []
    setForm((p) => ({
      ...p,
      title: (profile.title as string) ?? p.title,
      first_name: (profile.first_name as string) ?? p.first_name,
      last_name: (profile.last_name as string) ?? p.last_name,
      preferred_name: (profile.preferred_name as string) ?? p.preferred_name,
      dob_day,
      dob_month,
      dob_year,
      gender: (profile.gender as string) ?? p.gender,
      email: (profile.email as string) ?? p.email,
      address: (profile.address as string) ?? p.address,
      address_line2: (profile.address_line2 as string) ?? p.address_line2,
      city: (profile.city as string) ?? p.city,
      country: (profile.country as string) ?? p.country,
      postcode: (profile.postcode as string) ?? p.postcode,
      phone: (profile.phone as string) ?? p.phone,
      cell_number: (profile.cell_number as string) ?? p.cell_number,
      nationality: (profile.nationality as string) ?? p.nationality,
      second_nationality: (profile.second_nationality as string) ?? p.second_nationality,
      linkedin_url: (profile.linkedin_url as string) ?? p.linkedin_url,
      portfolio_url: (profile.portfolio_url as string) ?? p.portfolio_url,
      summary: (profile.summary as string) ?? p.summary,
      skills: skillsArray.length ? skillsArray.join(', ') : (p as any).skills ?? '',
      experience_years: profile.experience_years ?? p.experience_years,
      education_level: (profile.education_level as string) ?? p.education_level,
      current_position: (profile.current_position as string) ?? p.current_position,
      location: (profile.location as string) ?? p.location,
      cover_letter: fromApplication && myApplicationData && 'application' in myApplicationData && myApplicationData.application?.cover_letter != null
        ? String(myApplicationData.application.cover_letter)
        : p.cover_letter,
    }))
    const educationList = Array.isArray(profile.education) ? profile.education : (profile.education ? [profile.education] : [])
    setEducation(
      educationList.length > 0
        ? educationList.map((e: Record<string, unknown>) => ({
            education_type: (e.education_type as string) ?? '',
            degree_type: (e.degree_type as string) ?? '',
            discipline: (e.discipline as string) ?? '',
            other_specializations: (e.other_specializations as string) ?? '',
            country: (e.country as string) ?? '',
            institution: (e.institution as string) ?? '',
            city_campus: (e.city_campus as string) ?? '',
            study_level: (e.study_level as string) ?? '',
            enrollment_status: (e.enrollment_status as string) ?? '',
            start_year: (e.start_year as string) ?? '',
            end_year: (e.end_year as string) ?? '',
          }))
        : [emptyEdu()]
    )
    const experienceList = Array.isArray(profile.experience) ? profile.experience : (profile.experience ? [profile.experience] : [])
    setExperience(
      experienceList.length > 0
        ? experienceList.map((e: Record<string, unknown>) => ({
            employment_status: (e.employment_status as string) ?? '',
            employment_type: (e.employment_type as string) ?? '',
            employment_type_details: (e.employment_type_details as string) ?? '',
            job_title: (e.job_title as string) ?? '',
            job_contract_type: (e.job_contract_type as string) ?? '',
            job_level: (e.job_level as string) ?? '',
            responsibilities: (e.responsibilities as string) ?? '',
            start_month: (e.start_month as string) ?? '',
            start_year: (e.start_year as string) ?? '',
            start_day: (e.start_day as string) ?? '',
            end_month: (e.end_month as string) ?? '',
            end_year: (e.end_year as string) ?? '',
            end_day: (e.end_day as string) ?? '',
            company_name: (e.company_name as string) ?? '',
            company_sector: (e.company_sector as string) ?? '',
            country: (e.country as string) ?? '',
            city: (e.city as string) ?? '',
            department: (e.department as string) ?? '',
            manager_name: (e.manager_name as string) ?? '',
          }))
        : [emptyExp()]
    )
    const languagesList = Array.isArray(profile.languages) ? profile.languages : (profile.languages ? [profile.languages] : [])
    setLanguages(
      languagesList.length > 0
        ? languagesList.map((l: Record<string, unknown>) => ({
            language: (l.language as string) ?? '',
            speaking_proficiency: (l.speaking_proficiency as string) ?? '',
            reading_proficiency: (l.reading_proficiency as string) ?? '',
            writing_proficiency: (l.writing_proficiency as string) ?? '',
          }))
        : [emptyLang()]
    )
    const referencesList = Array.isArray(profile.references) ? profile.references : (profile.references ? [profile.references] : [])
    const refs = referencesList.length > 0
      ? referencesList.map((r: Record<string, unknown>) => ({
          first_name: (r.first_name as string) ?? '',
          last_name: (r.last_name as string) ?? '',
          organization: (r.organization as string) ?? '',
          job_title: (r.job_title as string) ?? '',
          phone: (r.phone as string) ?? '',
          email: (r.email as string) ?? '',
        }))
      : [emptyRef(), emptyRef(), emptyRef()]
    setReferences(refs)
  }, [user, profileData, myApplicationData])

  const applyMutation = useMutation({
    mutationFn: async (arg: FormData | Record<string, unknown> | { payload: FormData | Record<string, unknown>; isDraft?: boolean }) => {
      const payload = arg && typeof arg === 'object' && 'payload' in arg
        ? (arg as { payload: FormData | Record<string, unknown> }).payload
        : (arg as FormData | Record<string, unknown>)
      const isDraft = arg && typeof arg === 'object' && 'isDraft' in arg
        ? (arg as { isDraft: boolean }).isDraft === true
        : false
      const res = await applicationsApi.publicApply(payload as FormData)
      return { ...res, isDraft }
    },
    onSuccess: (res: { data?: { message?: string }; isDraft?: boolean }) => {
      queryClient.invalidateQueries({ queryKey: ['candidateProfile'] })
      queryClient.invalidateQueries({ queryKey: ['myApplicationByJob', slug] })
      if (res?.isDraft) {
        setCurrentStep((s) => s + 1)
        setShowDraftSaved(true)
        window.setTimeout(() => setShowDraftSaved(false), 2500)
        return
      }
      setSuccess(res?.data?.message ?? t('publicJob.applySuccess'))
    },
  })

  if (!user) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-12 dark:bg-slate-900">
        <div className="mx-auto max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {t('publicJob.loginRequired')}
          </h1>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            {t('publicJob.loginRequiredHint')}
          </p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Link
              to={applyUrl ? `/login?next=${encodeURIComponent(applyUrl)}` : '/login'}
              className="inline-flex justify-center rounded-lg bg-teal-600 px-4 py-2.5 font-medium text-white hover:bg-teal-700"
            >
              {t('nav.login')}
            </Link>
            <Link
              to={applyUrl ? `/register/candidate?next=${encodeURIComponent(applyUrl)}` : '/register/candidate'}
              className="inline-flex justify-center rounded-lg border border-slate-300 px-4 py-2.5 font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              {t('auth.createAccount')}
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="min-h-screen bg-slate-50 px-4 py-12 dark:bg-slate-900">
        <div className="mx-auto max-w-lg rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {t('publicJob.notFound')}
          </h1>
          <p className="mt-2 text-slate-600 dark:text-slate-400">
            {t('publicJob.notFoundHint')}
          </p>
          {slug && (
            <Link to={`/offres/${slug}`} className="mt-4 inline-block text-teal-600 hover:underline dark:text-teal-400">
              {t('common.back')}
            </Link>
          )}
        </div>
      </div>
    )
  }

  if (isExpired) {
    return (
      <div className="min-h-screen bg-slate-50 px-4 py-12 dark:bg-slate-900">
        <div className="mx-auto max-w-lg rounded-xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h1 className="text-xl font-bold text-amber-800 dark:text-amber-200">
            {t('publicJob.offerExpired')}
          </h1>
          <p className="mt-2 text-slate-600 dark:text-slate-400">
            {t('publicJob.offerExpiredHint')}
          </p>
          {slug && (
            <Link
              to={`/offres/${slug}`}
              className="mt-6 inline-flex items-center gap-2 text-teal-600 hover:underline dark:text-teal-400"
            >
              <ArrowLeft className="h-4 w-4" />
              {t('publicJob.backToOffer')}
            </Link>
          )}
        </div>
      </div>
    )
  }

  // Attendre le chargement (candidature existante ou profil) pour pré-remplir le formulaire
  const prefillLoading = profileQueryEnabled && (myApplicationLoading || (profileLoading && !myApplicationData))
  if (prefillLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-12 dark:bg-slate-900">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
        <p className="mt-4 text-sm text-slate-600 dark:text-slate-400">
          {t('publicJob.loadingProfile')}
        </p>
      </div>
    )
  }

  const isListEmpty = <T extends Record<string, string>>(
    list: T[],
    keys: (keyof T)[]
  ): boolean =>
    list.length === 0 ||
    list.every((item) => keys.every((k) => !(item[k] ?? '').toString().trim()))

  const detectCvConflicts = (data: CvParsedFormData): string[] => {
    const conflicts: string[] = []
    type CvScalarKey = 'email' | 'phone' | 'cell_number' | 'first_name' | 'last_name' | 'summary' | 'education_level' | 'current_position'
    const scalarChecks: Array<{ key: CvScalarKey; labelKey: string }> = [
      { key: 'email', labelKey: 'emailAddress' },
      { key: 'phone', labelKey: 'phoneNumber' },
      { key: 'cell_number', labelKey: 'cellNumber' },
      { key: 'first_name', labelKey: 'firstNameAsPassport' },
      { key: 'last_name', labelKey: 'lastNameAsPassport' },
      { key: 'summary', labelKey: 'coverLetter' },
      { key: 'education_level', labelKey: 'degree' },
      { key: 'current_position', labelKey: 'experience' },
    ]
    for (const { key, labelKey } of scalarChecks) {
      const cur = String(form[key] ?? '').trim()
      const incoming = String(data[key] ?? '').trim()
      if (cur && incoming && cur.toLowerCase() !== incoming.toLowerCase()) {
        const label = t(`publicJob.${labelKey}`)
        if (!conflicts.includes(label)) conflicts.push(label)
      }
    }
    const curLinkedin = (form.linkedin_url ?? '').trim()
    const incomingLinkedin = (data.linkedin_url ?? '').trim()
    if (curLinkedin && incomingLinkedin && curLinkedin.toLowerCase() !== incomingLinkedin.toLowerCase()) {
      conflicts.push('LinkedIn')
    }
    if (
      form.experience_years !== '' &&
      data.experience_years != null &&
      Number(form.experience_years) !== Number(data.experience_years)
    ) {
      conflicts.push(t('publicJob.experience'))
    }
    if (
      !isListEmpty(education, ['institution', 'degree_type', 'discipline', 'start_year']) &&
      (data.education?.length ?? 0) > 0
    ) {
      conflicts.push(t('publicJob.education'))
    }
    if (
      !isListEmpty(experience, ['job_title', 'company_name', 'responsibilities']) &&
      (data.experience?.length ?? 0) > 0
    ) {
      conflicts.push(t('publicJob.experience'))
    }
    if (
      !isListEmpty(languages, ['language', 'speaking_proficiency']) &&
      (data.languages?.length ?? 0) > 0
    ) {
      conflicts.push(t('publicJob.languages'))
    }
    if (
      !isListEmpty(references, ['first_name', 'last_name', 'email']) &&
      (data.references?.length ?? 0) > 0
    ) {
      conflicts.push(t('publicJob.references'))
    }
    const currentSkills = (form.skills ?? '').split(/[,;\n]/).map((s) => s.trim()).filter(Boolean)
    const incomingSkills = Array.isArray(data.skills)
      ? data.skills
      : typeof data.skills === 'string'
        ? data.skills.split(/[,;\n]/).map((s) => s.trim()).filter(Boolean)
        : []
    if (
      currentSkills.length > 0 &&
      incomingSkills.length > 0 &&
      incomingSkills.some((s) => !currentSkills.some((c) => c.toLowerCase() === s.toLowerCase()))
    ) {
      conflicts.push(t('publicJob.skills'))
    }
    return [...new Set(conflicts)]
  }

  const applyCvFormData = (data: CvParsedFormData, options?: { overwrite?: boolean }) => {
    const overwrite = options?.overwrite === true
    const dob = data.date_of_birth
    let dob_day = ''
    let dob_month = ''
    let dob_year = ''
    if (dob && /^\d{4}-\d{2}-\d{2}$/.test(dob)) {
      const [y, m, d] = dob.split('-')
      dob_year = y
      dob_day = String(Number(d))
      const monthNum = Number(m)
      if (monthNum >= 1 && monthNum <= 12) dob_month = MONTHS[monthNum - 1]
    }
    const skillsRaw = data.skills
    const skillsArray = Array.isArray(skillsRaw)
      ? skillsRaw
      : typeof skillsRaw === 'string'
        ? skillsRaw.split(/[,;\n]/).map((s) => s.trim()).filter((s) => s.length > 0)
        : []

    setForm((p) => {
      const merge = (key: keyof typeof p, value: string | number | undefined | null) => {
        if (value == null || value === '') return p[key]
        if (overwrite) return value as typeof p[typeof key]
        const cur = p[key]
        const empty = cur === '' || cur == null
        if (!empty) return cur
        return value as typeof cur
      }
      const mergedSkills = (() => {
        if (!skillsArray.length) return p.skills
        if (overwrite) return skillsArray.join(', ')
        const current = (p.skills ?? '').split(/[,;\n]/).map((s) => s.trim()).filter(Boolean)
        if (!current.length) return skillsArray.join(', ')
        const seen = new Set(current.map((s) => s.toLowerCase()))
        const extra = skillsArray.filter((s) => !seen.has(s.toLowerCase()))
        return [...current, ...extra].join(', ')
      })()
      const mergedExpYears = (() => {
        if (data.experience_years == null) return p.experience_years
        if (overwrite) return data.experience_years
        return p.experience_years !== '' ? p.experience_years : data.experience_years
      })()
      return {
        ...p,
        title: merge('title', data.title) as string,
        first_name: merge('first_name', data.first_name) as string,
        last_name: merge('last_name', data.last_name) as string,
        preferred_name: merge('preferred_name', data.preferred_name) as string,
        dob_day: overwrite && dob_day ? dob_day : (p.dob_day || dob_day),
        dob_month: overwrite && dob_month ? dob_month : (p.dob_month || dob_month),
        dob_year: overwrite && dob_year ? dob_year : (p.dob_year || dob_year),
        gender: merge('gender', data.gender) as string,
        email: merge('email', data.email) as string,
        address: merge('address', data.address) as string,
        address_line2: merge('address_line2', data.address_line2) as string,
        city: merge('city', data.city) as string,
        country: merge('country', data.country) as string,
        postcode: merge('postcode', data.postcode) as string,
        phone: merge('phone', data.phone) as string,
        cell_number: merge('cell_number', data.cell_number) as string,
        nationality: merge('nationality', data.nationality) as string,
        second_nationality: merge('second_nationality', data.second_nationality) as string,
        linkedin_url: merge('linkedin_url', data.linkedin_url) as string,
        portfolio_url: merge('portfolio_url', data.portfolio_url) as string,
        summary: merge('summary', data.summary) as string,
        skills: mergedSkills,
        experience_years: mergedExpYears,
        education_level: merge('education_level', data.education_level) as string,
        current_position: merge('current_position', data.current_position) as string,
        location: merge('location', data.location) as string,
      }
    })

    const eduList = Array.isArray(data.education) ? data.education : []
    if (
      eduList.length > 0 &&
      (overwrite || isListEmpty(education, ['institution', 'degree_type', 'discipline', 'start_year']))
    ) {
      setEducation(
        eduList.map((e) => ({
          education_type: (e.education_type as string) ?? '',
          degree_type: (e.degree_type as string) ?? '',
          discipline: (e.discipline as string) ?? '',
          other_specializations: (e.other_specializations as string) ?? '',
          country: (e.country as string) ?? '',
          institution: (e.institution as string) ?? '',
          city_campus: (e.city_campus as string) ?? '',
          study_level: (e.study_level as string) ?? '',
          enrollment_status: (e.enrollment_status as string) ?? '',
          start_year: (e.start_year as string) ?? '',
          end_year: (e.end_year as string) ?? '',
        }))
      )
    }

    const expList = Array.isArray(data.experience) ? data.experience : []
    if (
      expList.length > 0 &&
      (overwrite || isListEmpty(experience, ['job_title', 'company_name', 'responsibilities']))
    ) {
      setExperience(
        expList.map((e) => ({
          employment_status: (e.employment_status as string) ?? '',
          employment_type: (e.employment_type as string) ?? '',
          employment_type_details: (e.employment_type_details as string) ?? '',
          job_title: (e.job_title as string) ?? '',
          job_contract_type: (e.job_contract_type as string) ?? '',
          job_level: (e.job_level as string) ?? '',
          responsibilities: (e.responsibilities as string) ?? '',
          start_month: (e.start_month as string) ?? '',
          start_year: (e.start_year as string) ?? '',
          start_day: (e.start_day as string) ?? '',
          end_month: (e.end_month as string) ?? '',
          end_year: (e.end_year as string) ?? '',
          end_day: (e.end_day as string) ?? '',
          company_name: (e.company_name as string) ?? '',
          company_sector: (e.company_sector as string) ?? '',
          country: (e.country as string) ?? '',
          city: (e.city as string) ?? '',
          department: (e.department as string) ?? '',
          manager_name: (e.manager_name as string) ?? '',
        }))
      )
    }

    const langList = Array.isArray(data.languages) ? data.languages : []
    if (
      langList.length > 0 &&
      (overwrite || isListEmpty(languages, ['language', 'speaking_proficiency']))
    ) {
      setLanguages(
        langList.map((l) => ({
          language: (l.language as string) ?? '',
          speaking_proficiency: (l.speaking_proficiency as string) ?? '',
          reading_proficiency: (l.reading_proficiency as string) ?? '',
          writing_proficiency: (l.writing_proficiency as string) ?? '',
        }))
      )
    }

    const refList = Array.isArray(data.references) ? data.references : []
    if (
      refList.length > 0 &&
      (overwrite || isListEmpty(references, ['first_name', 'last_name', 'email']))
    ) {
      const refs = refList.map((r) => ({
        first_name: (r.first_name as string) ?? '',
        last_name: (r.last_name as string) ?? '',
        organization: (r.organization as string) ?? '',
        job_title: (r.job_title as string) ?? '',
        phone: (r.phone as string) ?? '',
        email: (r.email as string) ?? '',
      }))
      while (refs.length < 3) refs.push(emptyRef())
      setReferences(refs)
    }
  }

  const fetchResumeAsFile = async (url: string, filename: string): Promise<File | null> => {
    try {
      const res = await fetch(url, { credentials: 'include' })
      if (!res.ok) return null
      const blob = await res.blob()
      return new File([blob], filename || 'cv.pdf', { type: blob.type || 'application/pdf' })
    } catch {
      return null
    }
  }

  const finalizeCvAutofill = (
    res: ParseCvResponse,
    resumeFileToSet: File | null,
    successMessage: string,
    overwrite = false
  ) => {
    applyCvFormData(res.form_data, { overwrite })
    if (resumeFileToSet) setResumeFile(resumeFileToSet)
    setCvSectionConfidence(res.section_confidence ?? {})
    setCvAutofillWarnings(res.warnings ?? [])
    setCvAutofillMessage(successMessage)
    setPendingCvAutofill(null)
  }

  const handleCvParseResult = (
    res: ParseCvResponse,
    resumeFileToSet: File | null,
    successMessage: string
  ) => {
    const conflicts = detectCvConflicts(res.form_data)
    if (conflicts.length > 0) {
      setPendingCvAutofill({
        formData: res.form_data,
        sectionConfidence: res.section_confidence ?? {},
        warnings: res.warnings ?? [],
        resumeFile: resumeFileToSet,
        conflicts,
        successMessage,
      })
      return
    }
    finalizeCvAutofill(res, resumeFileToSet, successMessage, false)
  }

  const handleCvAutofillUpload = async (file: File) => {
    setCvParsing(true)
    setCvAutofillError(null)
    setCvAutofillMessage(null)
    setCvAutofillWarnings([])
    setPendingCvAutofill(null)
    try {
      const res = await applicationsApi.parseCv(file)
      handleCvParseResult(res.data, file, t('publicJob.cvAutofillSuccess'))
    } catch (e: unknown) {
      setCvAutofillError(getApiErrorMessage(e))
    } finally {
      setCvParsing(false)
    }
  }

  const handleUseLastCv = async () => {
    setCvParsing(true)
    setCvAutofillError(null)
    setCvAutofillMessage(null)
    setCvAutofillWarnings([])
    setPendingCvAutofill(null)
    try {
      const res = await applicationsApi.parseLastCv(slug ? { exclude_job_slug: slug } : undefined)
      let file: File | null = null
      if (res.data.resume_url) {
        file = await fetchResumeAsFile(
          res.data.resume_url,
          res.data.resume_filename || 'cv.pdf'
        )
      }
      handleCvParseResult(res.data, file, t('publicJob.cvAutofillFromLastSuccess'))
    } catch (e: unknown) {
      setCvAutofillError(getApiErrorMessage(e))
    } finally {
      setCvParsing(false)
    }
  }

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value, type } = e.target
    const checked = (e.target as HTMLInputElement).checked
    if (name === 'signature_text' || name === 'signature_agree') setSignatureError(null)
    setForm((p) => ({
      ...p,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  const buildPayload = (): FormData | Record<string, unknown> => {
    let date_of_birth: string | undefined
    if (form.dob_year && form.dob_month && form.dob_day) {
      const monthIndex = MONTHS.indexOf(form.dob_month)
      if (monthIndex >= 0) {
        const monthNum = String(monthIndex + 1).padStart(2, '0')
        date_of_birth = `${form.dob_year}-${monthNum}-${String(form.dob_day).padStart(2, '0')}`
      }
    }
    const normalizedSkills = (form.skills ?? '')
      .split(/[,;\n]/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0)
    const base: Record<string, unknown> = {
      job_offer_slug: slug,
      email: form.email,
      first_name: form.first_name,
      last_name: form.last_name,
      title: form.title,
      preferred_name: form.preferred_name,
      date_of_birth,
      gender: form.gender,
      address: form.address,
      address_line2: form.address_line2,
      city: form.city,
      country: form.country,
      postcode: form.postcode,
      phone: form.phone,
      cell_number: form.cell_number,
      nationality: form.nationality,
      second_nationality: form.second_nationality,
      cover_letter: form.cover_letter,
      linkedin_url: form.linkedin_url,
      portfolio_url: form.portfolio_url,
      summary: form.summary,
      skills: normalizedSkills.length ? normalizedSkills : undefined,
      education_level: form.education_level,
      current_position: form.current_position,
      location: form.location,
      education: education.filter((e) =>
        e.education_type || e.degree_type || e.discipline || e.institution || e.start_year || e.end_year
      ),
      experience: experience.filter((e) =>
        e.job_title || e.company_name || e.responsibilities || e.manager_name
      ),
      languages: languages.filter((l) =>
        l.language || l.speaking_proficiency || l.reading_proficiency || l.writing_proficiency
      ),
      references: references.filter((r) =>
        r.first_name || r.last_name || r.email || r.job_title
      ),
      allow_contact_references: form.allow_contact_references || undefined,
      signature_text: form.signature_agree ? form.signature_text : '',
    }
    if (form.experience_years !== '') base.experience_years = Number(form.experience_years)

    if (resumeFile || coverLetterFile) {
      const fd = new FormData()
      Object.entries(base).forEach(([k, v]) => {
        if (v === undefined || v === null) return
        if (typeof v === 'object' && !(v instanceof File)) fd.append(k, JSON.stringify(v))
        else fd.append(k, String(v))
      })
      if (resumeFile) fd.append('resume', resumeFile)
      if (coverLetterFile) fd.append('cover_letter_document', coverLetterFile)
      return fd
    }
    return base
  }

  const validateSignature = (): boolean => {
    setSignatureError(null)
    const sig = (form.signature_text ?? '').trim()
    if (!form.signature_agree || !sig) {
      setSignatureError(t('publicJob.signatureRequired'))
      setCurrentStep(totalSteps - 1)
      return false
    }
    const first = (form.first_name ?? '').trim()
    const last = (form.last_name ?? '').trim()
    const email = (form.email ?? '').trim().toLowerCase()
    const nameSignature = `${first} ${last}`.trim().toLowerCase().replace(/\s+/g, ' ')
    const sigNorm = sig.toLowerCase().replace(/\s+/g, ' ')
    const matchesName = nameSignature.length > 0 && sigNorm === nameSignature
    const matchesEmail = email.length > 0 && sigNorm === email.toLowerCase()
    if (!matchesName && !matchesEmail) {
      setSignatureError(t('publicJob.signatureMustMatch'))
      setCurrentStep(totalSteps - 1)
      return false
    }
    return true
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!slug || !job) return
    if (!validateSignature()) return
    applyMutation.mutate(buildPayload())
  }

  const handleNext = () => {
    if (!slug || !job) return
    applyMutation.mutate({ payload: buildPayload(), isDraft: true })
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Link
          to={`/offres/${slug}`}
          className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-teal-600 hover:text-teal-700 dark:text-teal-400"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('publicJob.backToOffer')}
        </Link>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {t('publicJob.applyTitle')} — {job.title}
          </h1>
          {success ? (
            <div className="mt-6 space-y-4">
              <p className="rounded-lg bg-teal-50 p-4 text-teal-800 dark:bg-teal-900/30 dark:text-teal-200">
                {success}
              </p>
              <Link
                to={`/offres/${slug}`}
                className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 font-medium text-white hover:bg-teal-700"
              >
                <ArrowLeft className="h-4 w-4" />
                {t('publicJob.backToOffer')}
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="mt-6 space-y-6">
              {myApplicationData && myApplicationData.job_still_open && (
                <div className="rounded-lg border border-teal-200 bg-teal-50 p-4 text-sm text-teal-800 dark:border-teal-700 dark:bg-teal-900/30 dark:text-teal-200">
                  {t('publicJob.alreadyAppliedBanner')}
                </div>
              )}
              {showDraftSaved && (
                <div className="rounded-lg border border-teal-200 bg-teal-50 p-3 text-sm text-teal-800 dark:border-teal-700 dark:bg-teal-900/30 dark:text-teal-200">
                  {t('publicJob.progressSaved')}
                </div>
              )}
              {signatureError && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200">
                  {signatureError}
                </div>
              )}
              {applyMutation.error && (
                <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
                  {isAxiosError(applyMutation.error) &&
                  (applyMutation.error.code === 'ERR_NETWORK' || !applyMutation.error.response)
                    ? t('publicJob.uploadNetworkError')
                    : isAxiosError(applyMutation.error) && applyMutation.error.response?.status === 413
                      ? t('publicJob.uploadFileTooLarge')
                      : getApiErrorMessage(applyMutation.error)}
                </div>
              )}

              <div className="rounded-xl border border-teal-200 bg-gradient-to-br from-teal-50/80 to-slate-50 p-4 dark:border-teal-800 dark:from-teal-950/40 dark:to-slate-800/60">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-lg bg-teal-100 p-2 dark:bg-teal-900/50">
                    <Sparkles className="h-5 w-5 text-teal-700 dark:text-teal-300" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                      {t('publicJob.cvAutofillTitle')}
                    </h2>
                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                      {t('publicJob.cvAutofillHint')}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-teal-600 px-3 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-60">
                        <FileUp className="h-4 w-4" />
                        <span>{cvParsing ? t('publicJob.cvAutofillParsing') : t('publicJob.cvAutofillUpload')}</span>
                        <input
                          ref={cvAutofillInputRef}
                          type="file"
                          accept=".pdf,.doc,.docx,.odt,.rtf,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                          className="hidden"
                          disabled={cvParsing}
                          onChange={(e) => {
                            const f = e.target.files?.[0]
                            if (f) void handleCvAutofillUpload(f)
                            e.target.value = ''
                          }}
                        />
                      </label>
                      {lastCvInfo?.available && (
                        <button
                          type="button"
                          disabled={cvParsing}
                          onClick={() => void handleUseLastCv()}
                          className="inline-flex items-center gap-2 rounded-lg border border-teal-300 bg-white px-3 py-2 text-sm font-medium text-teal-800 hover:bg-teal-50 disabled:opacity-60 dark:border-teal-700 dark:bg-slate-800 dark:text-teal-200 dark:hover:bg-slate-700"
                        >
                          {t('publicJob.cvAutofillUseLast')}
                        </button>
                      )}
                    </div>
                    {lastCvInfo?.available && lastCvInfo.job_title && (
                      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                        {t('publicJob.cvAutofillLastJob', { job: lastCvInfo.job_title })}
                      </p>
                    )}
                    {cvAutofillMessage && (
                      <p className="mt-2 text-xs font-medium text-teal-800 dark:text-teal-200">
                        {cvAutofillMessage}
                      </p>
                    )}
                    {cvAutofillError && (
                      <p className="mt-2 text-xs text-red-600 dark:text-red-400">{cvAutofillError}</p>
                    )}
                    {cvAutofillWarnings.length > 0 && (
                      <ul className="mt-2 list-inside list-disc text-xs text-amber-700 dark:text-amber-300">
                        {cvAutofillWarnings.slice(0, 3).map((w) => (
                          <li key={w}>{w}</li>
                        ))}
                      </ul>
                    )}
                    {Object.keys(cvSectionConfidence).length > 0 && (
                      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                        {t('publicJob.cvConfidenceLegend')}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {pendingCvAutofill && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
                  <div
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="cv-overwrite-title"
                    className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-600 dark:bg-slate-800"
                  >
                    <h3
                      id="cv-overwrite-title"
                      className="text-base font-semibold text-slate-800 dark:text-slate-100"
                    >
                      {t('publicJob.cvAutofillOverwriteTitle')}
                    </h3>
                    <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                      {t('publicJob.cvAutofillOverwriteHint')}
                    </p>
                    <ul className="mt-3 list-inside list-disc text-sm text-amber-800 dark:text-amber-200">
                      {pendingCvAutofill.conflicts.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                    <div className="mt-5 flex flex-wrap justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setPendingCvAutofill(null)}
                        className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
                      >
                        {t('publicJob.cvAutofillCancel')}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          finalizeCvAutofill(
                            {
                              form_data: pendingCvAutofill.formData,
                              section_confidence: pendingCvAutofill.sectionConfidence,
                              warnings: pendingCvAutofill.warnings,
                              source: 'upload',
                            },
                            pendingCvAutofill.resumeFile,
                            pendingCvAutofill.successMessage,
                            false
                          )
                        }
                        className="rounded-lg border border-teal-300 bg-teal-50 px-3 py-2 text-sm font-medium text-teal-800 hover:bg-teal-100 dark:border-teal-700 dark:bg-teal-900/30 dark:text-teal-200"
                      >
                        {t('publicJob.cvAutofillFillEmptyOnly')}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          finalizeCvAutofill(
                            {
                              form_data: pendingCvAutofill.formData,
                              section_confidence: pendingCvAutofill.sectionConfidence,
                              warnings: pendingCvAutofill.warnings,
                              source: 'upload',
                            },
                            pendingCvAutofill.resumeFile,
                            pendingCvAutofill.successMessage,
                            true
                          )
                        }
                        className="rounded-lg bg-teal-600 px-3 py-2 text-sm font-medium text-white hover:bg-teal-700"
                      >
                        {t('publicJob.cvAutofillReplaceAll')}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Indicateur d'étapes */}
              <div className="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-4 dark:border-slate-600">
                {FORM_SECTIONS.map((key, idx) => {
                  const confKey = key as CvAutofillSectionKey
                  const badge =
                    key !== 'signature'
                      ? confidenceBadge(cvSectionConfidence[confKey], t)
                      : null
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setCurrentStep(idx)}
                      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                        currentStep === idx
                          ? 'bg-teal-600 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                      }`}
                    >
                      <span>
                        {idx + 1}. {t(`publicJob.${key}`)}
                      </span>
                      {badge && (
                        <span
                          className={`rounded px-1 py-0.5 text-[10px] font-normal leading-none ${
                            currentStep === idx ? 'bg-white/20 text-white' : badge.cls
                          }`}
                          title={badge.label}
                        >
                          {badge.label}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>

              {currentStep === 0 && (
              <section>
                <h3 className="mb-1 text-base font-bold text-slate-800 dark:text-slate-100">
                  {t('publicJob.personalDetails')}
                </h3>
                <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
                  {t('publicJob.personalDetailsHint')}
                </p>
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.title')} *
                      </label>
                      <select
                        name="title"
                        value={form.title}
                        onChange={handleChange}
                        required
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      >
                        <option value="">—</option>
                        {TITLES.map((opt) => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.firstNameAsPassport')} *
                      </label>
                      <input
                        name="first_name"
                        value={form.first_name}
                        onChange={handleChange}
                        required
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.lastNameAsPassport')} *
                      </label>
                      <input
                        name="last_name"
                        value={form.last_name}
                        onChange={handleChange}
                        required
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.preferredName')}
                    </label>
                    <input
                      name="preferred_name"
                      value={form.preferred_name}
                      onChange={handleChange}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.dateOfBirth')} *
                    </label>
                    <div className="flex gap-2">
                      <select
                        name="dob_day"
                        value={form.dob_day}
                        onChange={handleChange}
                        required
                        className="flex-1 rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      >
                        <option value="">{t('publicJob.day')}</option>
                        {DAYS.map((d) => (
                          <option key={d} value={d}>{d}</option>
                        ))}
                      </select>
                      <select
                        name="dob_month"
                        value={form.dob_month}
                        onChange={handleChange}
                        required
                        className="flex-1 rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      >
                        <option value="">{t('publicJob.month')}</option>
                        {MONTHS.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                      <select
                        name="dob_year"
                        value={form.dob_year}
                        onChange={handleChange}
                        required
                        className="flex-1 rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      >
                        <option value="">{t('publicJob.year')}</option>
                        {YEARS.map((y) => (
                          <option key={y} value={y}>{y}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.gender')} *
                    </label>
                    <select
                      name="gender"
                      value={form.gender}
                      onChange={handleChange}
                      required
                      className="w-full max-w-xs rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    >
                      <option value="">—</option>
                      {GENDERS.map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.emailAddress')} *
                    </label>
                    <input
                      name="email"
                      type="email"
                      value={form.email}
                      onChange={handleChange}
                      required
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.currentAddress')} *
                    </label>
                    <input
                      name="address"
                      value={form.address}
                      onChange={handleChange}
                      required
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.currentAddressLine2')}
                    </label>
                    <input
                      name="address_line2"
                      value={form.address_line2}
                      onChange={handleChange}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.city')} *
                    </label>
                    <input
                      name="city"
                      value={form.city}
                      onChange={handleChange}
                      required
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                </div>
                <hr className="my-6 border-slate-200 dark:border-slate-600" />
                <div className="space-y-4">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.country')} *
                    </label>
                    <input
                      name="country"
                      value={form.country}
                      onChange={handleChange}
                      required
                      placeholder="e.g. Congo, The Democratic Republic Of The"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.cityProvince')} *
                    </label>
                    <input
                      name="city"
                      value={form.city}
                      onChange={handleChange}
                      required
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.postcode')}
                    </label>
                    <input
                      name="postcode"
                      value={form.postcode}
                      onChange={handleChange}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                </div>
                <hr className="my-6 border-slate-200 dark:border-slate-600" />
                <div className="space-y-4">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.phoneNumber')} *
                    </label>
                    <input
                      name="phone"
                      type="tel"
                      value={form.phone}
                      onChange={handleChange}
                      required
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.cellNumber')}
                    </label>
                    <input
                      name="cell_number"
                      type="tel"
                      value={form.cell_number}
                      onChange={handleChange}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                </div>
                <hr className="my-6 border-slate-200 dark:border-slate-600" />
                <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-300">
                  {t('publicJob.selectNationalities')}
                </p>
                <div className="space-y-4">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.nationality')} *
                    </label>
                    <input
                      name="nationality"
                      value={form.nationality}
                      onChange={handleChange}
                      required
                      placeholder="e.g. Congolese (DRC)"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.secondNationality')}
                    </label>
                    <input
                      name="second_nationality"
                      value={form.second_nationality}
                      onChange={handleChange}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                </div>
              </section>
              )}

              {currentStep === 1 && (
              <section>
                <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {t('publicJob.education')}
                </h3>
                {education.map((e, i) => (
                  <div key={i} className="mb-6 space-y-4 rounded-lg border border-slate-200 p-4 dark:border-slate-600">
                    <div className="grid gap-4 sm:grid-cols-3">
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.educationType')} *
                        </label>
                        <select
                          value={e.education_type}
                          onChange={(ev) =>
                            setEducation((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], education_type: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          <option value="">—</option>
                          {EDUCATION_TYPES.map((opt) => (
                            <option key={opt} value={opt}>{t(`publicJob.eduEducationType_${opt}`)}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.degreeType')} *
                        </label>
                        <select
                          value={e.degree_type}
                          onChange={(ev) =>
                            setEducation((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], degree_type: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          <option value="">—</option>
                          {DEGREE_TYPES.map((opt) => (
                            <option key={opt} value={opt}>{t(`publicJob.eduDegreeType_${opt}`)}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.discipline')} *
                        </label>
                        <select
                          value={e.discipline}
                          onChange={(ev) =>
                            setEducation((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], discipline: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          <option value="">—</option>
                          {DISCIPLINES.map((opt) => (
                            <option key={opt} value={opt}>{t(`publicJob.eduDiscipline_${opt}`)}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.otherSpecializations')}
                      </label>
                      <input
                        value={e.other_specializations}
                        onChange={(ev) =>
                          setEducation((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], other_specializations: ev.target.value }
                            return n
                          })
                        }
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.country')} *
                      </label>
                      <input
                        value={e.country}
                        onChange={(ev) =>
                          setEducation((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], country: ev.target.value }
                            return n
                          })
                        }
                        placeholder="e.g. Congo, The Democratic Republic Of The"
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.institution')} *
                      </label>
                      <input
                        value={e.institution}
                        onChange={(ev) =>
                          setEducation((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], institution: ev.target.value }
                            return n
                          })
                        }
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.cityCampus')} *
                      </label>
                      <input
                        value={e.city_campus}
                        onChange={(ev) =>
                          setEducation((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], city_campus: ev.target.value }
                            return n
                          })
                        }
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.studyLevel')} *
                        </label>
                        <select
                          value={e.study_level}
                          onChange={(ev) =>
                            setEducation((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], study_level: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          <option value="">—</option>
                          {STUDY_LEVELS.map((opt) => (
                            <option key={opt} value={opt}>{t(`publicJob.eduStudyLevel_${opt}`)}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.enrollmentStatus')}
                        </label>
                        <select
                          value={e.enrollment_status}
                          onChange={(ev) =>
                            setEducation((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], enrollment_status: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          <option value="">—</option>
                          {ENROLLMENT_STATUSES.map((opt) => (
                            <option key={opt} value={opt}>{t(`publicJob.eduEnrollmentStatus_${opt}`)}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.startYear')} *
                        </label>
                        <input
                          type="date"
                          value={e.start_year ? `${e.start_year}-09-01` : ''}
                          onChange={(ev) => {
                            const val = ev.target.value
                            const year = val ? val.slice(0, 4) : ''
                            setEducation((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], start_year: year }
                              return n
                            })
                          }}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.endYear')} *
                        </label>
                        <input
                          type="date"
                          value={e.end_year ? `${e.end_year}-06-30` : ''}
                          onChange={(ev) => {
                            const val = ev.target.value
                            const year = val ? val.slice(0, 4) : ''
                            setEducation((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], end_year: year }
                              return n
                            })
                          }}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      </div>
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setEducation((p) => [...p, emptyEdu()])}
                  className="text-sm text-teal-600 hover:underline dark:text-teal-400"
                >
                  + {t('publicJob.addEducation')}
                </button>
              </section>
              )}

              {currentStep === 2 && (
              <section>
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    {t('publicJob.experience')} — {t('publicJob.jobDetails')}
                  </h3>
                </div>
                {experience.map((e, i) => (
                  <div key={i} className="mb-6 space-y-4 rounded-lg border border-slate-200 p-4 dark:border-slate-600">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.employmentStatus')} *
                        </label>
                        <select
                          value={e.employment_status}
                          onChange={(ev) =>
                            setExperience((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], employment_status: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          <option value="">—</option>
                          {EMPLOYMENT_STATUSES.map((opt) => (
                            <option key={opt} value={opt}>{t(`publicJob.expEmploymentStatus_${opt}`)}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.employmentType')} *
                        </label>
                        <select
                          value={e.employment_type}
                          onChange={(ev) =>
                            setExperience((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], employment_type: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          <option value="">—</option>
                          {EMPLOYMENT_TYPES.map((opt) => (
                            <option key={opt} value={opt}>{t(`publicJob.expEmploymentType_${opt}`)}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.employmentTypeDetails')}
                      </label>
                      <select
                        value={e.employment_type_details}
                        onChange={(ev) =>
                          setExperience((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], employment_type_details: ev.target.value }
                            return n
                          })
                        }
                        className="w-full max-w-xs rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      >
                        <option value="">—</option>
                        {EMPLOYMENT_TYPE_DETAILS.map((opt) => (
                          <option key={opt} value={opt}>{t(`publicJob.expTypeDetails_${opt}`)}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.jobTitle')} *
                      </label>
                      <input
                        value={e.job_title}
                        onChange={(ev) =>
                          setExperience((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], job_title: ev.target.value }
                            return n
                          })
                        }
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.jobContractType')} *
                        </label>
                        <select
                          value={e.job_contract_type}
                          onChange={(ev) =>
                            setExperience((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], job_contract_type: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          <option value="">—</option>
                          {JOB_CONTRACT_TYPES.map((opt) => (
                            <option key={opt} value={opt}>{t(`publicJob.expContractType_${opt}`)}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.jobLevel')}
                        </label>
                        <select
                          value={e.job_level}
                          onChange={(ev) =>
                            setExperience((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], job_level: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          <option value="">—</option>
                          {JOB_LEVELS.map((opt) => (
                            <option key={opt} value={opt}>{t(`publicJob.expJobLevel_${opt}`)}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.responsibilities')} *
                      </label>
                      <textarea
                        value={e.responsibilities}
                        onChange={(ev) =>
                          setExperience((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], responsibilities: ev.target.value }
                            return n
                          })
                        }
                        rows={4}
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.startDateInCompany')} *
                        </label>
                        <input
                          type="date"
                          value={
                            e.start_year && e.start_month
                              ? `${e.start_year}-${String(MONTHS.indexOf(e.start_month) + 1).padStart(2, '0')}-${(e.start_day || '01').padStart(2, '0')}`
                              : ''
                          }
                          onChange={(ev) => {
                            const val = ev.target.value
                            if (!val) {
                              setExperience((prev) => {
                                const n = [...prev]
                                n[i] = { ...n[i], start_month: '', start_year: '', start_day: '' }
                                return n
                              })
                              return
                            }
                            const y = val.slice(0, 4)
                            const m = parseInt(val.slice(5, 7), 10)
                            const d = val.slice(8, 10)
                            const monthName = m >= 1 && m <= 12 ? MONTHS[m - 1] : ''
                            setExperience((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], start_month: monthName, start_year: y, start_day: d }
                              return n
                            })
                          }}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.endDateInCompany')}
                        </label>
                        <input
                          type="date"
                          value={
                            e.end_year && e.end_month
                              ? `${e.end_year}-${String(MONTHS.indexOf(e.end_month) + 1).padStart(2, '0')}-${(e.end_day || '01').padStart(2, '0')}`
                              : e.end_year
                                ? `${e.end_year}-12-01`
                                : ''
                          }
                          onChange={(ev) => {
                            const val = ev.target.value
                            if (!val) {
                              setExperience((prev) => {
                                const n = [...prev]
                                n[i] = { ...n[i], end_month: '', end_year: '', end_day: '' }
                                return n
                              })
                              return
                            }
                            const y = val.slice(0, 4)
                            const m = parseInt(val.slice(5, 7), 10)
                            const d = val.slice(8, 10)
                            const monthName = m >= 1 && m <= 12 ? MONTHS[m - 1] : ''
                            setExperience((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], end_month: monthName, end_year: y, end_day: d }
                              return n
                            })
                          }}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.companyName')} *
                      </label>
                      <input
                        value={e.company_name}
                        onChange={(ev) =>
                          setExperience((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], company_name: ev.target.value }
                            return n
                          })
                        }
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.companySector')} *
                      </label>
                      <select
                        value={e.company_sector}
                        onChange={(ev) =>
                          setExperience((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], company_sector: ev.target.value }
                            return n
                          })
                        }
                        className="w-full max-w-xs rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      >
                        <option value="">—</option>
                        {COMPANY_SECTORS.map((opt) => (
                          <option key={opt} value={opt}>{t(`publicJob.expSector_${opt}`)}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.countryOfEmployment')} *
                      </label>
                      <input
                        value={e.country}
                        onChange={(ev) =>
                          setExperience((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], country: ev.target.value }
                            return n
                          })
                        }
                        placeholder="e.g. Congo, The Democratic Republic Of The"
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.cityOfEmployment')} *
                      </label>
                      <input
                        value={e.city}
                        onChange={(ev) =>
                          setExperience((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], city: ev.target.value }
                            return n
                          })
                        }
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.departmentAssignment')}
                      </label>
                      <input
                        value={e.department}
                        onChange={(ev) =>
                          setExperience((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], department: ev.target.value }
                            return n
                          })
                        }
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.managerName')} *
                      </label>
                      <input
                        value={e.manager_name}
                        onChange={(ev) =>
                          setExperience((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], manager_name: ev.target.value }
                            return n
                          })
                        }
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setExperience((p) => [...p, emptyExp()])}
                  className="text-sm text-teal-600 hover:underline dark:text-teal-400"
                >
                  + {t('publicJob.addExperience')}
                </button>
              </section>
              )}

              {currentStep === 3 && (
              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {t('publicJob.skills')}
                </h3>
                <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
                  {t('publicJob.skillsHint')}
                </p>
                <textarea
                  name="skills"
                  value={form.skills}
                  onChange={handleChange}
                  rows={4}
                  placeholder={t('publicJob.skillsPlaceholder')}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </section>
              )}

              {currentStep === 4 && (
              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {t('publicJob.languages')}
                </h3>
                <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
                  {t('publicJob.languagesHint')}
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[600px] border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-600">
                        <th className="pb-2 pr-2 text-left font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.language')}
                        </th>
                        <th className="pb-2 pr-2 text-left font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.speakingProficiency')} *
                        </th>
                        <th className="pb-2 pr-2 text-left font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.readingProficiency')} *
                        </th>
                        <th className="pb-2 text-left font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.writingProficiency')} *
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {languages.map((l, i) => (
                        <tr key={i} className="border-b border-slate-100 dark:border-slate-700">
                          <td className="py-2 pr-2 align-top">
                            <span className="mb-1 block text-xs text-slate-500 dark:text-slate-400">
                              {t('publicJob.languageN', { n: i + 1 })}
                            </span>
                            <select
                              value={l.language}
                              onChange={(ev) =>
                                setLanguages((prev) => {
                                  const n = [...prev]
                                  n[i] = { ...n[i], language: ev.target.value }
                                  return n
                                })
                              }
                              className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                            >
                              <option value="">—</option>
                              {LANGUAGES_LIST.map((opt) => (
                                <option key={opt} value={opt}>{t(`publicJob.lang_${opt}`)}</option>
                              ))}
                            </select>
                          </td>
                          <td className="py-2 pr-2 align-top">
                            <select
                              value={l.speaking_proficiency}
                              onChange={(ev) =>
                                setLanguages((prev) => {
                                  const n = [...prev]
                                  n[i] = { ...n[i], speaking_proficiency: ev.target.value }
                                  return n
                                })
                              }
                              className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                            >
                              <option value="">—</option>
                              {PROFICIENCY_LEVELS.map((opt) => (
                                <option key={opt} value={opt}>{t(`publicJob.prof_${opt}`)}</option>
                              ))}
                            </select>
                          </td>
                          <td className="py-2 pr-2 align-top">
                            <select
                              value={l.reading_proficiency}
                              onChange={(ev) =>
                                setLanguages((prev) => {
                                  const n = [...prev]
                                  n[i] = { ...n[i], reading_proficiency: ev.target.value }
                                  return n
                                })
                              }
                              className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                            >
                              <option value="">—</option>
                              {PROFICIENCY_LEVELS.map((opt) => (
                                <option key={opt} value={opt}>{t(`publicJob.prof_${opt}`)}</option>
                              ))}
                            </select>
                          </td>
                          <td className="py-2 align-top">
                            <select
                              value={l.writing_proficiency}
                              onChange={(ev) =>
                                setLanguages((prev) => {
                                  const n = [...prev]
                                  n[i] = { ...n[i], writing_proficiency: ev.target.value }
                                  return n
                                })
                              }
                              className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                            >
                              <option value="">—</option>
                              {PROFICIENCY_LEVELS.map((opt) => (
                                <option key={opt} value={opt}>{t(`publicJob.prof_${opt}`)}</option>
                              ))}
                            </select>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <button
                  type="button"
                  onClick={() => setLanguages((p) => [...p, emptyLang()])}
                  className="mt-4 text-sm text-teal-600 hover:underline dark:text-teal-400"
                >
                  + {t('publicJob.addMore')}
                </button>
              </section>
              )}

              {currentStep === 5 && (
              <section>
                <h3 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {t('publicJob.references')} — {t('publicJob.referencesDetails')}
                </h3>
                <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
                  {t('publicJob.referencesHint')}
                </p>
                <div className="mb-6">
                  <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-300">
                    {t('publicJob.allowContactRefQuestion')} *
                  </p>
                  <div className="flex flex-wrap gap-4">
                    <label className="flex cursor-pointer items-center gap-2">
                      <input
                        type="radio"
                        name="allow_contact_references"
                        value="yes"
                        checked={form.allow_contact_references === 'yes'}
                        onChange={handleChange}
                        className="border-slate-300 text-teal-600"
                      />
                      <span className="text-sm text-slate-700 dark:text-slate-300">
                        {t('publicJob.allowContactYes')}
                      </span>
                    </label>
                    <label className="flex cursor-pointer items-center gap-2">
                      <input
                        type="radio"
                        name="allow_contact_references"
                        value="no"
                        checked={form.allow_contact_references === 'no'}
                        onChange={handleChange}
                        className="border-slate-300 text-teal-600"
                      />
                      <span className="text-sm text-slate-700 dark:text-slate-300">
                        {t('publicJob.allowContactNo')}
                      </span>
                    </label>
                  </div>
                </div>
                {references.map((r, i) => (
                  <div key={i} className="mb-6 rounded-lg border border-slate-200 p-4 dark:border-slate-600">
                    <h4 className="mb-3 text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.refereeN', { n: i + 1 })}
                    </h4>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.refFirstName')} *
                        </label>
                        <input
                          value={r.first_name}
                          onChange={(ev) =>
                            setReferences((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], first_name: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.refLastName')} *
                        </label>
                        <input
                          value={r.last_name}
                          onChange={(ev) =>
                            setReferences((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], last_name: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      </div>
                    </div>
                    <div className="mt-4">
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.refOrganization')}
                      </label>
                      <input
                        value={r.organization}
                        onChange={(ev) =>
                          setReferences((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], organization: ev.target.value }
                            return n
                          })
                        }
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div className="mt-4">
                      <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        {t('publicJob.refJobTitle')} *
                      </label>
                      <input
                        value={r.job_title}
                        onChange={(ev) =>
                          setReferences((prev) => {
                            const n = [...prev]
                            n[i] = { ...n[i], job_title: ev.target.value }
                            return n
                          })
                        }
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                    <div className="mt-4 grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.refPhone')}
                        </label>
                        <input
                          type="tel"
                          value={r.phone}
                          onChange={(ev) =>
                            setReferences((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], phone: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          {t('publicJob.refEmail')} *
                        </label>
                        <input
                          type="email"
                          value={r.email}
                          onChange={(ev) =>
                            setReferences((prev) => {
                              const n = [...prev]
                              n[i] = { ...n[i], email: ev.target.value }
                              return n
                            })
                          }
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      </div>
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setReferences((p) => [...p, emptyRef()])}
                  className="text-sm text-teal-600 hover:underline dark:text-teal-400"
                >
                  + {t('publicJob.addReference')}
                </button>
              </section>
              )}

              {currentStep === 6 && (
              <section>
                <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {t('publicJob.documents')}
                </h3>
                <div className="space-y-6">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.coverLetter')}
                    </label>
                    <textarea
                      name="cover_letter"
                      value={form.cover_letter}
                      onChange={handleChange}
                      rows={4}
                      placeholder={t('publicJob.coverLetter')}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    />
                  </div>
                  <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-600">
                    <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.coverLetterDoc')}
                    </label>
                    <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
                      {t('publicJob.importCoverLetter')}
                    </p>
                    <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600">
                      <span>{t('jobs.chooseFile')}</span>
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        onChange={(e) => setCoverLetterFile(e.target.files?.[0] ?? null)}
                        className="hidden"
                      />
                    </label>
                    <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
                      {coverLetterFile
                        ? coverLetterFile.name
                        : myApplicationData?.application?.cover_letter_document_url
                          ? (
                              <>
                                {t('publicJob.existingFileDeposited')}{' '}
                                <a
                                  href={myApplicationData.application.cover_letter_document_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="font-medium text-primary-600 underline hover:text-primary-700 dark:text-primary-400"
                                >
                                  {t('publicJob.downloadExistingFile')}
                                </a>
                              </>
                            )
                          : t('publicJob.noFileChosen')}
                    </p>
                  </div>
                  <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-600">
                    <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                      {t('publicJob.resume')}
                    </label>
                    <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
                      {t('publicJob.importResume')}
                    </p>
                    <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600">
                      <span>{t('jobs.chooseFile')}</span>
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
                        className="hidden"
                      />
                    </label>
                    <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
                      {resumeFile
                        ? resumeFile.name
                        : myApplicationData?.candidate?.resume_url
                          ? (
                              <>
                                {t('publicJob.existingFileDeposited')}{' '}
                                <a
                                  href={myApplicationData.candidate.resume_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="font-medium text-primary-600 underline hover:text-primary-700 dark:text-primary-400"
                                >
                                  {t('publicJob.downloadExistingFile')}
                                </a>
                              </>
                            )
                          : t('publicJob.noFileChosen')}
                    </p>
                  </div>
                </div>
              </section>
              )}

              {currentStep === 7 && (
              <section>
                <h3 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-300">
                  {t('publicJob.signature')}
                </h3>
                <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
                  {t('publicJob.signatureHint')}
                </p>
                <input
                  name="signature_text"
                  value={form.signature_text}
                  onChange={(e) => {
                    handleChange(e)
                    if (signatureError) setSignatureError(null)
                  }}
                  placeholder={t('publicJob.signaturePlaceholder')}
                  className={`mb-2 w-full rounded-lg border px-3 py-2 dark:bg-slate-700 dark:text-slate-100 ${
                    signatureError ? 'border-amber-500 dark:border-amber-500' : 'border-slate-300 dark:border-slate-600'
                  }`}
                />
                {signatureError && currentStep === 7 && (
                  <p className="mb-2 text-sm text-amber-600 dark:text-amber-400">{signatureError}</p>
                )}
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    name="signature_agree"
                    checked={form.signature_agree}
                    onChange={handleChange}
                    className="rounded border-slate-300"
                  />
                  <span className="text-sm text-slate-700 dark:text-slate-300">
                    {t('publicJob.signatureAgree')}
                  </span>
                </label>
              </section>
              )}

              <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-slate-200 pt-6 dark:border-slate-600">
                <div>
                  {currentStep > 0 ? (
                    <button
                      type="button"
                      onClick={() => setCurrentStep((s) => s - 1)}
                      className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
                    >
                      {t('common.previous')}
                    </button>
                  ) : (
                    <Link
                      to={`/offres/${slug}`}
                      className="inline-flex items-center rounded-lg border border-slate-300 px-4 py-2 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
                    >
                      {t('common.back')}
                    </Link>
                  )}
                </div>
                <div>
                  {isLastStep ? (
                    <button
                      type="submit"
                      disabled={applyMutation.isPending}
                      className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                    >
                      <Send className="h-4 w-4" />
                      {applyMutation.isPending ? t('common.loading') : t('publicJob.submit')}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={handleNext}
                      disabled={applyMutation.isPending}
                      className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                    >
                      {applyMutation.isPending ? t('common.loading') : t('common.next')}
                    </button>
                  )}
                </div>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
