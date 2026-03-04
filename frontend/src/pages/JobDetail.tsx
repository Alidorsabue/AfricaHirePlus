/**
 * Page Détail offre : onglets Candidatures, Présélection, Sélection, Dashboard.
 * Critères de présélection (règles de scoring + paramètres) dans l'onglet Présélection.
 * Critères de sélection (avancés) dans l'onglet Sélection.
 */
import { useState, useMemo, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useQueries, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  FileDown,
  Plus,
  Minus,
  Pencil,
  Lock,
  RefreshCw,
  Users,
  TrendingUp,
  BarChart3,
  Trash2,
} from 'lucide-react'
import { jobsApi } from '../api/jobs'
import { applicationsApi } from '../api/applications'
import { unwrapList } from '../api/utils'
import { useToast } from '../contexts/ToastContext'
import type {
  Application,
  JobOffer,
  LeaderboardEntry,
  ShortlistEntry,
  JobKpi,
  ScreeningRule,
  PreselectionScoreDetail,
  AtsBreakdown,
} from '../types'

const RULE_TYPES = [
  { value: 'keywords', labelKey: 'ruleTypeKeywords' },
  { value: 'min_experience', labelKey: 'ruleTypeMinExperience' },
  { value: 'education_level', labelKey: 'ruleTypeEducationLevel' },
  { value: 'location', labelKey: 'ruleTypeLocation' },
  { value: 'custom', labelKey: 'ruleTypeCustom' },
] as const
type RuleType = (typeof RULE_TYPES)[number]['value']
interface ScreeningRuleForm {
  rule_type: RuleType
  value: Record<string, unknown>
  weight: string
  is_required: boolean
  order: number
}

type TabId = 'applications' | 'cvAnalysis' | 'preselection' | 'selection' | 'dashboard'

const TAB_IDS: TabId[] = ['applications', 'cvAnalysis', 'preselection', 'selection', 'dashboard']

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function getCandidateName(candidate: { first_name?: string; last_name?: string } | number): string {
  if (typeof candidate === 'number') return '—'
  const first = candidate?.first_name ?? ''
  const last = candidate?.last_name ?? ''
  return [first, last].filter(Boolean).join(' ') || '—'
}

function getStatusLabel(status: string, t: (k: string) => string): string {
  const key = `pipeline.${status}` as const
  const out = t(key)
  return out !== key ? out : status
}

export default function JobDetail() {
  const { id } = useParams<{ id: string }>()
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const jobId = id ? parseInt(id, 10) : NaN
  const [activeTab, setActiveTab] = useState<TabId>('applications')
  const [closeModalOpen, setCloseModalOpen] = useState(false)
  const [editScoreAppId, setEditScoreAppId] = useState<number | null>(null)
  const [editScoreValue, setEditScoreValue] = useState('')
  const [forceStatusAppId, setForceStatusAppId] = useState<number | null>(null)
  const [forceStatusValue, setForceStatusValue] = useState('')

  const [screeningRules, setScreeningRules] = useState<ScreeningRuleForm[]>([])
  const [preselectionThreshold, setPreselectionThreshold] = useState('60')
  const [preselectionMaxCandidates, setPreselectionMaxCandidates] = useState('')
  const [selectionThreshold, setSelectionThreshold] = useState('60')
  const [selectionMaxCandidates, setSelectionMaxCandidates] = useState('')
  const [selectionModeLocal, setSelectionModeLocal] = useState<'auto' | 'semi_automatic'>('semi_automatic')
  const [selectionRules, setSelectionRules] = useState<ScreeningRuleForm[]>([])

  /** Mots-clés identifiés éditables par le recruteur avant ajout aux règles (un par ligne ou virgule) */
  const [editablePreselectionKeywords, setEditablePreselectionKeywords] = useState('')

  const isJobIdValid = Number.isFinite(jobId) && jobId > 0

  const { data: job, isLoading: jobLoading, error: jobError } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.get(jobId).then((r) => r.data),
    enabled: isJobIdValid,
  })

  const { data: applications = [], isLoading: appsLoading } = useQuery({
    queryKey: ['applications', 'job', jobId],
    queryFn: async () =>
      unwrapList((await applicationsApi.list({ job_offer: jobId })).data),
    enabled: isJobIdValid,
  })

  const { data: applicationsWithCv = [], isLoading: appsWithCvLoading } = useQuery({
    queryKey: ['applications', 'job', jobId, 'with_cv'],
    queryFn: async () =>
      unwrapList((await applicationsApi.list({ job_offer: jobId, with_cv: true })).data),
    enabled: isJobIdValid && activeTab === 'cvAnalysis',
  })

  // Détail ATS chargé à la demande par candidat (évite de bloquer l’affichage de la liste)
  const breakdownQueries = useQueries({
    queries: (applicationsWithCv ?? []).map((app) => ({
      queryKey: ['ats-breakdown', app.id],
      queryFn: () => applicationsApi.getAtsBreakdown(app.id),
      enabled: activeTab === 'cvAnalysis' && !!app.id,
    })),
  })
  const breakdownByAppId = useMemo(() => {
    const m: Record<number, AtsBreakdown> = {}
    applicationsWithCv.forEach((app, i) => {
      const data = breakdownQueries[i]?.data
      if (data) m[app.id] = data
    })
    return m
  }, [applicationsWithCv, breakdownQueries])

  const refetchIntervalLeaderboard = activeTab === 'preselection' ? 10_000 : false
  const { data: leaderboard = [], isLoading: leaderboardLoading } = useQuery({
    queryKey: ['leaderboard', jobId],
    queryFn: () => jobsApi.getLeaderboard(jobId).then((r) => r.data),
    enabled: isJobIdValid && activeTab === 'preselection',
    refetchInterval: refetchIntervalLeaderboard,
  })

  const { data: kpi, isLoading: kpiLoading } = useQuery({
    queryKey: ['jobKpi', jobId],
    queryFn: () => jobsApi.getKpi(jobId).then((r) => r.data),
    enabled: isJobIdValid && activeTab === 'dashboard',
  })

  const [generatedShortlist, setGeneratedShortlist] = useState<ShortlistEntry[] | null>(null)
  const [shortlistLoading, setShortlistLoading] = useState(false)

  useEffect(() => {
    if (!job) return
    const j = job as JobOffer
    if (j.screening_rules?.length) {
      setScreeningRules(
        j.screening_rules.map((r: ScreeningRule, i: number) => {
          const val = r.value || {}
          let displayValue = { ...val }
          if (r.rule_type === 'keywords' && Array.isArray(val.keywords)) {
            displayValue = { ...val, keywords: (val.keywords as string[]).join('\n') }
          }
          return {
            rule_type: (r.rule_type || 'keywords') as RuleType,
            value: displayValue,
            weight: String(r.weight ?? 10),
            is_required: r.is_required ?? true,
            order: r.order ?? i,
          }
        })
      )
    } else {
      setScreeningRules([])
    }
    const pre = j.preselection_settings
    setPreselectionThreshold(pre?.score_threshold != null ? String(pre.score_threshold) : '60')
    setPreselectionMaxCandidates(pre?.max_candidates != null ? String(pre.max_candidates) : '')
    const sel = j.selection_settings
    setSelectionThreshold(sel?.score_threshold != null ? String(sel.score_threshold) : '60')
    setSelectionMaxCandidates(sel?.max_candidates != null ? String(sel.max_candidates) : '')
    setSelectionModeLocal((sel?.selection_mode as 'auto' | 'semi_automatic') ?? j.selection_mode ?? 'semi_automatic')
    const selRules = sel?.selection_rules
    if (Array.isArray(selRules) && selRules.length > 0) {
      setSelectionRules(
        selRules.map((r: ScreeningRule, i: number) => {
          const val = r.value || {}
          let displayValue = { ...val }
          if (r.rule_type === 'keywords' && Array.isArray(val.keywords)) {
            displayValue = { ...val, keywords: (val.keywords as string[]).join('\n') }
          }
          return {
            rule_type: (r.rule_type || 'keywords') as RuleType,
            value: displayValue,
            weight: String(r.weight ?? 10),
            is_required: r.is_required ?? true,
            order: r.order ?? i,
          }
        })
      )
    } else {
      setSelectionRules([])
    }
    const suggestedKw = (j.suggested_criteria?.keywords ?? []) as string[]
    if (suggestedKw.length > 0) {
      setEditablePreselectionKeywords(suggestedKw.join('\n'))
    }
  }, [job])

  const buildScreeningRulesPayload = () =>
    screeningRules.map((r, i) => {
      let value: Record<string, unknown> = {}
      if (r.rule_type === 'keywords') {
        const raw = (r.value.keywords as string) ?? (r.value.keywords_list as string) ?? ''
        const list = typeof raw === 'string' ? raw.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean) : Array.isArray(raw) ? raw : []
        value = { keywords: list }
      } else if (r.rule_type === 'min_experience') {
        const years = Number((r.value.years ?? r.value.min_years ?? 0)) || 0
        value = { years }
      } else if (r.rule_type === 'education_level') {
        const level = String(r.value.level ?? r.value.education_level ?? '').trim()
        value = { level }
      } else {
        value = { ...r.value }
      }
      return {
        rule_type: r.rule_type,
        value,
        weight: Number(r.weight) || 10,
        is_required: r.is_required,
        order: i,
      }
    })

  const addPreselectionRule = () => {
    setScreeningRules((prev) => [
      ...prev,
      { rule_type: 'keywords', value: {}, weight: '10', is_required: true, order: prev.length },
    ])
  }

  const suggestedCriteria = (job as JobOffer)?.suggested_criteria
  const suggestedKeywords = suggestedCriteria?.keywords ?? []
  const suggestedMinExperience = suggestedCriteria?.min_experience ?? null
  const suggestedEducationLevel = suggestedCriteria?.education_level ?? null
  const hasSuggestedCriteria =
    suggestedKeywords.length > 0 || suggestedMinExperience != null || (suggestedEducationLevel != null && suggestedEducationLevel !== '')

  const parseEditableKeywords = (text: string) =>
    text
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter(Boolean)

  const addSuggestedKeywordsToPreselectionRules = () => {
    const list = parseEditableKeywords(editablePreselectionKeywords)
    if (list.length === 0) return
    const keywordsText = list.join('\n')
    setScreeningRules((prev) => [
      ...prev,
      { rule_type: 'keywords', value: { keywords: keywordsText }, weight: '10', is_required: true, order: prev.length },
    ])
  }
  const addSuggestedExperienceToPreselectionRules = () => {
    if (suggestedMinExperience == null) return
    setScreeningRules((prev) => [
      ...prev,
      { rule_type: 'min_experience', value: { years: suggestedMinExperience }, weight: '10', is_required: true, order: prev.length },
    ])
  }
  const addSuggestedEducationToPreselectionRules = () => {
    if (!suggestedEducationLevel) return
    setScreeningRules((prev) => [
      ...prev,
      { rule_type: 'education_level', value: { level: suggestedEducationLevel }, weight: '10', is_required: true, order: prev.length },
    ])
  }

  const removePreselectionRule = (index: number) => {
    setScreeningRules((prev) => prev.filter((_, i) => i !== index))
  }
  const updatePreselectionRule = (
    index: number,
    field: keyof ScreeningRuleForm,
    value: ScreeningRuleForm[keyof ScreeningRuleForm]
  ) => {
    setScreeningRules((prev) =>
      prev.map((r, i) => (i === index ? { ...r, [field]: value } : r))
    )
  }
  const updatePreselectionRuleValue = (index: number, key: string, value: unknown) => {
    setScreeningRules((prev) =>
      prev.map((r, i) => (i === index ? { ...r, value: { ...r.value, [key]: value } } : r))
    )
  }

  const buildSelectionRulesPayload = () =>
    selectionRules.map((r, i) => {
      let value: Record<string, unknown> = {}
      if (r.rule_type === 'keywords') {
        const raw = (r.value.keywords as string) ?? (r.value.keywords_list as string) ?? ''
        const list = typeof raw === 'string' ? raw.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean) : Array.isArray(raw) ? raw : []
        value = { keywords: list }
      } else if (r.rule_type === 'min_experience') {
        const years = Number((r.value.years ?? r.value.min_years ?? 0)) || 0
        value = { years }
      } else if (r.rule_type === 'education_level') {
        const level = String(r.value.level ?? r.value.education_level ?? '').trim()
        value = { level }
      } else {
        value = { ...r.value }
      }
      return {
        rule_type: r.rule_type,
        value,
        weight: Number(r.weight) || 10,
        is_required: r.is_required,
        order: i,
      }
    })

  const addSelectionRule = () => {
    setSelectionRules((prev) => [
      ...prev,
      { rule_type: 'keywords', value: {}, weight: '10', is_required: true, order: prev.length },
    ])
  }
  const removeSelectionRule = (index: number) => {
    setSelectionRules((prev) => prev.filter((_, i) => i !== index))
  }
  const updateSelectionRule = (
    index: number,
    field: keyof ScreeningRuleForm,
    value: ScreeningRuleForm[keyof ScreeningRuleForm]
  ) => {
    setSelectionRules((prev) =>
      prev.map((r, i) => (i === index ? { ...r, [field]: value } : r))
    )
  }
  const updateSelectionRuleValue = (index: number, key: string, value: unknown) => {
    setSelectionRules((prev) =>
      prev.map((r, i) => (i === index ? { ...r, value: { ...r.value, [key]: value } } : r))
    )
  }

  const savePreselectionMutation = useMutation({
    mutationFn: () =>
      jobsApi.update(jobId, {
        screening_rules: buildScreeningRulesPayload(),
        preselection_settings: {
          score_threshold: parseFloat(preselectionThreshold) || 60,
          max_candidates: preselectionMaxCandidates ? parseInt(preselectionMaxCandidates, 10) : null,
        },
      } as Partial<JobOffer>),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
      toast.success(t('common.saved'))
    },
    onError: (err: unknown) => {
      toast.error((err as Error).message || 'Erreur')
    },
  })

  const saveSelectionMutation = useMutation({
    mutationFn: () =>
      jobsApi.update(jobId, {
        selection_settings: {
          score_threshold: parseFloat(selectionThreshold) || 60,
          max_candidates: selectionMaxCandidates ? parseInt(selectionMaxCandidates, 10) : null,
          selection_mode: selectionModeLocal,
          selection_rules: buildSelectionRulesPayload(),
        },
        selection_mode: selectionModeLocal,
      } as Partial<JobOffer>),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
      toast.success(t('common.saved'))
    },
    onError: (err: unknown) => {
      toast.error((err as Error).message || 'Erreur')
    },
  })

  const closeJobMutation = useMutation({
    mutationFn: () => jobsApi.close(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      toast.success(t('jobs.closeOffer') + ' — OK')
      setCloseModalOpen(false)
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      const msg =
        err?.response?.data?.detail || (err as Error).message || 'Erreur'
      toast.error(msg)
    },
  })

  const manualOverrideMutation = useMutation({
    mutationFn: ({
      appId,
      action,
      reason,
      new_status,
      new_score,
    }: {
      appId: number
      action: 'ADD_TO_SHORTLIST' | 'REMOVE_FROM_SHORTLIST' | 'FORCE_STATUS' | 'UPDATE_SCORE'
      reason?: string
      new_status?: string
      new_score?: number
    }) =>
      applicationsApi.manualOverride(appId, {
        action,
        reason,
        new_status,
        new_score,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications', 'job', jobId] })
      queryClient.invalidateQueries({ queryKey: ['leaderboard', jobId] })
      toast.success(t('common.saved') || 'Enregistré')
      setEditScoreAppId(null)
      setForceStatusAppId(null)
    },
    onError: (err: { response?: { data?: Record<string, string[]> } }) => {
      const detail = err?.response?.data
      const msg =
        (detail && typeof detail === 'object' && 'detail' in detail
          ? String((detail as { detail?: string }).detail)
          : null) ||
        (detail && typeof detail === 'object' && Object.keys(detail).length
          ? JSON.stringify(detail)
          : (err as Error).message)
      toast.error(msg || 'Erreur')
    },
  })

  const refreshScoresMutation = useMutation({
    mutationFn: () => jobsApi.refreshScores(jobId),
    onSuccess: async (res) => {
      await queryClient.refetchQueries({ queryKey: ['applications', 'job', jobId] })
      queryClient.invalidateQueries({ queryKey: ['leaderboard', jobId] })
      queryClient.invalidateQueries({ queryKey: ['kpi', jobId] })
      const msg = (res as { data?: { message?: string } })?.data?.message
      toast.success(msg ?? t('common.saved'))
    },
    onError: (err: unknown) => {
      toast.error((err as Error).message || 'Erreur recalcul')
    },
  })

  const handleGenerateShortlist = async () => {
    setShortlistLoading(true)
    try {
      const { data } = await jobsApi.generateShortlist(jobId)
      setGeneratedShortlist(data.shortlist || [])
      queryClient.invalidateQueries({ queryKey: ['applications', 'job', jobId] })
      queryClient.invalidateQueries({ queryKey: ['leaderboard', jobId] })
      toast.success(t('jobs.shortlistGenerated'))
    } catch (err: unknown) {
      toast.error((err as Error).message || 'Erreur génération shortlist')
    } finally {
      setShortlistLoading(false)
    }
  }

  const handleExportPdf = async () => {
    try {
      const { data } = await jobsApi.exportShortlistPdf(jobId)
      downloadBlob(data as Blob, `shortlist_${jobId}.pdf`)
      toast.success(t('jobs.exportShortlistPdf') + ' — OK')
    } catch (err: unknown) {
      toast.error((err as Error).message || 'Erreur export PDF')
    }
  }

  const preselectedApplications = useMemo(
    () => applications.filter((a) => a.status === 'preselected'),
    [applications]
  )
  const shortlistedApplications = useMemo(
    () => applications.filter((a) => a.status === 'shortlisted'),
    [applications]
  )

  const scoreDistribution = useMemo(() => {
    const scores = applications
      .map((a) => a.preselection_score ?? a.selection_score)
      .filter((s): s is number => typeof s === 'number')
    if (scores.length === 0) return []
    const buckets = [0, 20, 40, 60, 80, 100]
    return buckets.slice(0, -1).map((low, i) => {
      const high = buckets[i + 1]
      const count = scores.filter((s) => s >= low && s < high).length
      return { label: `${low}-${high}`, count }
    })
  }, [applications])

  const applicationsByDate = useMemo(() => {
    const byDate: Record<string, number> = {}
    applications.forEach((a) => {
      const day = (a.applied_at || a.created_at || '').slice(0, 10)
      if (day) byDate[day] = (byDate[day] || 0) + 1
    })
    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, count]) => ({ date, count }))
  }, [applications])

  if (!isJobIdValid) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
        <p>ID d'offre invalide.</p>
        <Link to="/jobs" className="mt-2 inline-block text-teal-600 hover:underline">
          {t('jobs.title')}
        </Link>
      </div>
    )
  }

  if (jobLoading || jobError) {
    if (jobError) {
      return (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
          <p>Offre introuvable ou erreur.</p>
          <Link to="/jobs" className="mt-2 inline-block text-teal-600 hover:underline">
            {t('jobs.title')}
          </Link>
        </div>
      )
    }
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
      </div>
    )
  }

  const canClose = job && job.status !== 'closed'
  const selectionMode = selectionModeLocal

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/jobs"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
            aria-label={t('common.back')}
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
              {job?.title}
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t('jobs.detail')} · {job?.location || '—'} ·{' '}
              <span className="rounded bg-slate-100 px-1.5 py-0.5 dark:bg-slate-700">
                {t(`jobs.${job?.status || 'draft'}`)}
              </span>
            </p>
          </div>
        </div>
        <div className="flex flex-shrink-0 flex-wrap items-center justify-end gap-3">
          <div className="flex items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50/80 px-2 py-1.5 dark:border-slate-600/80 dark:bg-slate-800/60">
            <Link
              to={`/jobs/${jobId}/edit`}
              className="inline-flex h-9 items-center gap-2 rounded-lg px-3.5 text-sm font-medium text-slate-600 transition-colors hover:bg-white hover:text-slate-800 hover:shadow-sm dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-slate-100"
            >
              <Pencil className="h-4 w-4 shrink-0" />
              {t('jobs.edit')}
            </Link>
            {canClose && (
              <button
                type="button"
                onClick={() => setCloseModalOpen(true)}
                className="inline-flex h-9 items-center gap-2 rounded-lg px-3.5 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-50 hover:text-amber-800 dark:text-amber-300 dark:hover:bg-amber-900/40 dark:hover:text-amber-200"
              >
                {t('jobs.closeOffer')}
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={handleExportPdf}
            className="inline-flex h-9 items-center gap-2 rounded-xl bg-teal-600 px-4 py-2 text-sm font-medium text-white shadow-md transition-all hover:bg-teal-500 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 dark:bg-teal-500 dark:text-slate-900 dark:hover:bg-teal-400 dark:focus:ring-offset-slate-900"
          >
            <FileDown className="h-4 w-4 shrink-0" />
            {t('jobs.exportShortlistPdf')}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200 dark:border-slate-700">
        <nav className="-mb-px flex gap-4" aria-label="Onglets">
          {TAB_IDS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? 'border-teal-500 text-teal-600 dark:text-teal-400'
                  : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'
              }`}
            >
              {t(`jobs.tab${tab.charAt(0).toUpperCase() + tab.slice(1)}`)}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab: Candidatures */}
      {activeTab === 'applications' && (
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
            <h3 className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {t('jobs.tabApplications')}
            </h3>
            <button
              type="button"
              onClick={() => refreshScoresMutation.mutate()}
              disabled={refreshScoresMutation.isPending || applications.length === 0}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              <RefreshCw
                className={refreshScoresMutation.isPending ? 'h-4 w-4 animate-spin' : 'h-4 w-4'}
              />
              {t('jobs.refreshScores')}
            </button>
          </div>
          <div className="overflow-x-auto">
            {appsLoading ? (
              <div className="flex justify-center py-12">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
              </div>
            ) : applications.length === 0 ? (
              <p className="px-6 py-12 text-center text-slate-500">
                {t('jobs.noApplications')}
              </p>
            ) : (
              <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-600">
                <thead className="bg-slate-50 dark:bg-slate-800">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                      #
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                      {t('jobs.name')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                      {t('jobs.status')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                      {t('jobs.score')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                      Date
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-600">
                  {applications.map((app, idx) => (
                    <tr key={app.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/50">
                      <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
                        {idx + 1}
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-slate-900 dark:text-slate-100">
                        <Link
                          to={`/applications/${app.id}`}
                          className="text-teal-600 hover:underline dark:text-teal-400"
                        >
                          {getCandidateName(
                            typeof app.candidate === 'object' ? app.candidate : { first_name: '', last_name: '' }
                          )}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-600">
                          {getStatusLabel(app.status, t)}
                        </span>
                        {(app as Application).is_manually_adjusted && (
                          <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800 dark:bg-amber-900/50 dark:text-amber-200">
                            {t('jobs.overrideManual')}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
                        {(app as Application).preselection_score ??
                          (app as Application).selection_score ??
                          '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
                        {app.applied_at
                          ? new Date(app.applied_at).toLocaleDateString()
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {/* Tab: Analyse CV — Résumé raw_cv_text + analyse (preselection_score_details) par candidat */}
      {activeTab === 'cvAnalysis' && (
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-700">
            <h3 className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {t('jobs.tabCvAnalysis')}
            </h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {t('jobs.tabCvAnalysisHint')}
            </p>
          </div>
          <div className="p-4">
            {appsWithCvLoading ? (
              <div className="flex justify-center py-12">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
              </div>
            ) : applicationsWithCv.length === 0 ? (
              <p className="py-12 text-center text-slate-500">{t('jobs.noApplications')}</p>
            ) : (
              <div className="space-y-6">
                {applicationsWithCv.map((app, index) => {
                  const candidate = typeof app.candidate === 'object' ? app.candidate : null
                  const rawCv = candidate?.raw_cv_text ?? ''
                  const details = (app as Application).preselection_score_details as PreselectionScoreDetail[] | null | undefined
                  const hasDetails = Array.isArray(details) && details.length > 0
                  const ats = breakdownByAppId[app.id]
                  const atsLoading = breakdownQueries[index]?.isLoading === true
                  const hasAts = ats != null && typeof ats === 'object'
                  return (
                    <div
                      key={app.id}
                      className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-600 dark:bg-slate-800/30"
                    >
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3 dark:border-slate-600">
                        <div className="flex items-center gap-3">
                          <Link
                            to={`/applications/${app.id}`}
                            className="font-medium text-teal-600 hover:underline dark:text-teal-400"
                          >
                            {getCandidateName(candidate ?? 0)}
                          </Link>
                          <span className="rounded bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-600">
                            {getStatusLabel(app.status, t)}
                          </span>
                          {(app as Application).preselection_score != null && (
                            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                              Score : {(app as Application).preselection_score}
                            </span>
                          )}
                        </div>
                        {app.applied_at && (
                          <span className="text-xs text-slate-500 dark:text-slate-400">
                            {new Date(app.applied_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                      <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
                        <div>
                          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                            {t('jobs.cvSummary')}
                          </h4>
                          <div className="max-h-48 overflow-y-auto rounded border border-slate-200 bg-white p-3 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-300">
                            {rawCv ? (
                              <p className="whitespace-pre-wrap break-words">{rawCv}</p>
                            ) : (
                              <p className="italic text-slate-500 dark:text-slate-400">
                                {t('jobs.noCvText')}
                              </p>
                            )}
                          </div>
                        </div>
                        <div>
                          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                            {t('jobs.analysisBreakdown')}
                          </h4>
                          <div className="rounded border border-slate-200 bg-white p-3 dark:border-slate-600 dark:bg-slate-700/50">
                            {atsLoading ? (
                              <div className="flex items-center justify-center py-8">
                                <div className="h-6 w-6 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
                              </div>
                            ) : hasDetails ? (
                              <ul className="space-y-1.5 text-sm">
                                {details.map((d, i) => (
                                  <li
                                    key={i}
                                    className={`flex items-center justify-between gap-2 ${
                                      d.passed ? 'text-slate-700 dark:text-slate-300' : 'text-slate-500 dark:text-slate-400'
                                    }`}
                                  >
                                    <span className="truncate">
                                      {d.criterion ?? t('jobs.criterion')} :{' '}
                                      {d.passed ? t('jobs.passed') : t('jobs.notPassed')}
                                    </span>
                                    {d.weight_awarded != null && (
                                      <span className="shrink-0 font-medium">
                                        +{d.weight_awarded}
                                      </span>
                                    )}
                                  </li>
                                ))}
                              </ul>
                            ) : hasAts ? (
                              <div className="space-y-4 text-sm">
                                <div className="grid grid-cols-3 gap-2 text-xs font-medium">
                                  <span className="rounded bg-teal-50 px-2 py-1 text-teal-800 dark:bg-teal-900/40 dark:text-teal-200">
                                    {t('jobs.keywordScore')} : {((ats.keyword_score ?? 0) * 100).toFixed(1)} %
                                  </span>
                                  <span className="rounded bg-slate-100 px-2 py-1 text-slate-700 dark:bg-slate-600 dark:text-slate-200">
                                    {t('jobs.semanticScore')} : {((ats.semantic_score ?? 0) * 100).toFixed(1)} %
                                  </span>
                                  <span className="rounded bg-slate-200 px-2 py-1 text-slate-800 dark:bg-slate-500 dark:text-slate-100">
                                    {t('jobs.totalScore')} : {ats.total_score ?? '—'}
                                  </span>
                                </div>
                                {ats.categories && (
                                  <div className="space-y-3 border-t border-slate-200 pt-3 dark:border-slate-600">
                                    {(
                                      [
                                        ['mots_cles', 'jobs.catMotsCles'],
                                        ['niveau_etudes', 'jobs.catNiveauEtudes'],
                                        ['experience', 'jobs.catExperience'],
                                        ['competences', 'jobs.catCompetences'],
                                        ['localisation', 'jobs.catLocalisation'],
                                        ['langue', 'jobs.catLangue'],
                                        ['personnalise', 'jobs.catPersonnalise'],
                                      ] as const
                                    ).map(([key, labelKey]) => {
                                      const cat = ats.categories![key]
                                      if (!cat) return null
                                      const hasKw = (cat.keywords_found?.length ?? 0) > 0 || (cat.keywords_missing?.length ?? 0) > 0
                                      const hasReqCand = cat.required != null || cat.candidate != null || cat.match !== undefined
                                      if (!hasKw && !hasReqCand) return null
                                      return (
                                        <div key={key} className="rounded border border-slate-100 bg-slate-50/50 p-2 dark:border-slate-600 dark:bg-slate-800/30">
                                          <p className="mb-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400">
                                            {t(labelKey)}
                                          </p>
                                          {hasReqCand && (cat.required != null || cat.candidate != null || cat.match !== undefined) && (
                                            <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs">
                                              {cat.required_years != null && (
                                                <span>
                                                  {t('jobs.required')} : {cat.required_years} {t('jobs.years')}
                                                </span>
                                              )}
                                              {cat.candidate_years != null && (
                                                <span>
                                                  {t('jobs.candidate')} : {cat.candidate_years} {t('jobs.years')}
                                                </span>
                                              )}
                                              {cat.required != null && typeof cat.required === 'string' && (
                                                <span>{t('jobs.required')} : {cat.required}</span>
                                              )}
                                              {Array.isArray(cat.required) && cat.required.length > 0 && (
                                                <span>{t('jobs.required')} : {cat.required.join(', ')}</span>
                                              )}
                                              {cat.candidate != null && <span>{t('jobs.candidate')} : {String(cat.candidate)}</span>}
                                              {cat.match !== undefined && cat.match !== null && (
                                                <span
                                                  className={
                                                    cat.match
                                                      ? 'font-medium text-teal-600 dark:text-teal-400'
                                                      : 'text-slate-500 dark:text-slate-400'
                                                  }
                                                >
                                                  {cat.match ? t('jobs.passed') : t('jobs.notPassed')}
                                                </span>
                                              )}
                                            </div>
                                          )}
                                          {hasKw && (
                                            <>
                                              {cat.keywords_found && cat.keywords_found.length > 0 && (
                                                <div className="mb-1 flex flex-wrap gap-1">
                                                  {cat.keywords_found.slice(0, 25).map((kw, i) => (
                                                    <span
                                                      key={i}
                                                      className="rounded bg-teal-100 px-1.5 py-0.5 text-xs text-teal-800 dark:bg-teal-800/50 dark:text-teal-200"
                                                    >
                                                      {kw}
                                                    </span>
                                                  ))}
                                                  {(cat.keywords_found?.length ?? 0) > 25 && (
                                                    <span className="text-xs text-slate-500">+{(cat.keywords_found?.length ?? 0) - 25}</span>
                                                  )}
                                                </div>
                                              )}
                                              {cat.keywords_missing && cat.keywords_missing.length > 0 && (
                                                <div className="flex flex-wrap gap-1">
                                                  {cat.keywords_missing.slice(0, 15).map((kw, i) => (
                                                    <span
                                                      key={i}
                                                      className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600 dark:bg-slate-600 dark:text-slate-300"
                                                    >
                                                      {kw}
                                                    </span>
                                                  ))}
                                                  {(cat.keywords_missing?.length ?? 0) > 15 && (
                                                    <span className="text-xs text-slate-500">+{(cat.keywords_missing?.length ?? 0) - 15}</span>
                                                  )}
                                                </div>
                                              )}
                                            </>
                                          )}
                                        </div>
                                      )
                                    })}
                                  </div>
                                )}
                                {(!ats.categories || Object.keys(ats.categories).length === 0) && (
                                  <>
                                    {(ats.keywords_found?.length ?? 0) > 0 && (
                                      <div>
                                        <p className="mb-1.5 text-xs font-medium text-slate-600 dark:text-slate-400">
                                          {t('jobs.keywordsFoundInCv')}
                                        </p>
                                        <div className="flex flex-wrap gap-1.5">
                                          {(ats.keywords_found ?? []).map((kw, i) => (
                                            <span key={i} className="rounded bg-teal-100 px-2 py-0.5 text-xs text-teal-800 dark:bg-teal-800/50 dark:text-teal-200">
                                              {kw}
                                            </span>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                    {(ats.keywords_missing?.length ?? 0) > 0 && (
                                      <div>
                                        <p className="mb-1.5 text-xs font-medium text-slate-600 dark:text-slate-400">
                                          {t('jobs.keywordsMissingFromCv')}
                                        </p>
                                        <div className="flex flex-wrap gap-1.5">
                                          {(ats.keywords_missing ?? []).slice(0, 30).map((kw, i) => (
                                            <span key={i} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-600 dark:text-slate-300">
                                              {kw}
                                            </span>
                                          ))}
                                          {(ats.keywords_missing?.length ?? 0) > 30 && (
                                            <span className="text-xs text-slate-500">+{(ats.keywords_missing?.length ?? 0) - 30} {t('jobs.more')}</span>
                                          )}
                                        </div>
                                      </div>
                                    )}
                                  </>
                                )}
                              </div>
                            ) : (
                              <p className="text-sm italic text-slate-500 dark:text-slate-400">
                                {(app as Application).preselection_score != null
                                  ? t('jobs.analysisRuleBasedOrAts')
                                  : t('jobs.noAnalysisYet')}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Tab: Présélection — Critères + Leaderboard + Simulation + Ajustement manuel */}
      {activeTab === 'preselection' && (
        <div className="space-y-6">
          {/* Critères de présélection */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
            <h2 className="mb-1 text-base font-semibold text-slate-800 dark:text-slate-200">
              {t('jobs.preselectionCriteriaTitle')}
            </h2>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
              {t('jobs.preselectionCriteriaHint')}
            </p>

            {/* Critères identifiés à partir de l'offre (Présélection) */}
            {hasSuggestedCriteria && (
              <div className="mb-6 rounded-lg border border-teal-200 bg-teal-50/50 p-4 dark:border-teal-800 dark:bg-teal-900/20">
                <h3 className="mb-1 text-sm font-medium text-slate-800 dark:text-slate-200">
                  {t('jobs.criteriaIdentifiedFromOffer')}
                </h3>
                <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
                  {t('jobs.criteriaIdentifiedHint')}
                </p>
                <div className="mb-3">
                  <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
                    {t('jobs.editSuggestedKeywords')}
                  </label>
                  <textarea
                    value={editablePreselectionKeywords}
                    onChange={(e) => setEditablePreselectionKeywords(e.target.value)}
                    placeholder={t('jobs.keywordsPlaceholder')}
                    rows={5}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:placeholder-slate-400"
                  />
                  <button
                    type="button"
                    onClick={addSuggestedKeywordsToPreselectionRules}
                    disabled={parseEditableKeywords(editablePreselectionKeywords).length === 0}
                    className="mt-2 inline-flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                  >
                    <Plus className="h-4 w-4" />
                    {t('jobs.addToPreselectionRules')}
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {suggestedMinExperience != null && (
                    <span className="inline-flex items-center gap-2 rounded-md bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm dark:bg-slate-700 dark:text-slate-200">
                      {t('jobs.suggestedExperience')} : {t('jobs.yearsExperience', { count: suggestedMinExperience })}
                      <button
                        type="button"
                        onClick={addSuggestedExperienceToPreselectionRules}
                        className="rounded bg-teal-600 px-2 py-0.5 text-xs text-white hover:bg-teal-700"
                      >
                        {t('jobs.addAsRule')}
                      </button>
                    </span>
                  )}
                  {suggestedEducationLevel && (
                    <span className="inline-flex items-center gap-2 rounded-md bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm dark:bg-slate-700 dark:text-slate-200">
                      {t('jobs.suggestedEducation')} : {suggestedEducationLevel}
                      <button
                        type="button"
                        onClick={addSuggestedEducationToPreselectionRules}
                        className="rounded bg-teal-600 px-2 py-0.5 text-xs text-white hover:bg-teal-700"
                      >
                        {t('jobs.addAsRule')}
                      </button>
                    </span>
                  )}
                </div>
              </div>
            )}

            <div className="mb-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{t('jobs.screeningRules')}</span>
                <button
                  type="button"
                  onClick={addPreselectionRule}
                  className="inline-flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
                >
                  <Plus className="h-4 w-4" />
                  {t('jobs.addRule')}
                </button>
              </div>
              {screeningRules.length === 0 ? (
                <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 py-4 text-center text-sm text-slate-500 dark:border-slate-600 dark:bg-slate-800/50 dark:text-slate-400">
                  {t('jobs.noRulesHint')}
                </p>
              ) : (
                <ul className="space-y-4">
                  {screeningRules.map((rule, index) => (
                    <li
                      key={index}
                      className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-600 dark:bg-slate-800/30"
                    >
                      <div className="mb-3 flex flex-wrap items-center gap-3">
                        <select
                          value={rule.rule_type}
                          onChange={(e) => updatePreselectionRule(index, 'rule_type', e.target.value as RuleType)}
                          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          {RULE_TYPES.map((opt) => (
                            <option key={opt.value} value={opt.value}>{t(`jobs.${opt.labelKey}`)}</option>
                          ))}
                        </select>
                        <label className="flex items-center gap-2">
                          <span className="text-sm text-slate-600 dark:text-slate-300">{t('jobs.points')}</span>
                          <input
                            type="number"
                            min={0}
                            step={1}
                            value={rule.weight}
                            onChange={(e) => updatePreselectionRule(index, 'weight', e.target.value)}
                            className="w-20 rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                          />
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={rule.is_required}
                            onChange={(e) => updatePreselectionRule(index, 'is_required', e.target.checked)}
                            className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 dark:border-slate-600 dark:bg-slate-700 dark:text-teal-400"
                          />
                          <span className="text-sm text-slate-600 dark:text-slate-300">{t('jobs.required')}</span>
                        </label>
                        <button
                          type="button"
                          onClick={() => removePreselectionRule(index)}
                          className="ml-auto rounded p-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                          title={t('common.delete')}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                      {rule.rule_type === 'keywords' && (
                        <textarea
                          value={String(rule.value?.keywords ?? '')}
                          onChange={(e) => updatePreselectionRuleValue(index, 'keywords', e.target.value)}
                          placeholder={t('jobs.keywordsPlaceholder')}
                          rows={3}
                          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:placeholder-slate-400"
                        />
                      )}
                      {rule.rule_type === 'min_experience' && (
                        <input
                          type="number"
                          min={0}
                          value={String(rule.value?.years ?? rule.value?.min_years ?? '')}
                          onChange={(e) => updatePreselectionRuleValue(index, 'years', e.target.value)}
                          placeholder={t('jobs.yearsPlaceholder')}
                          className="w-32 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      )}
                      {rule.rule_type === 'education_level' && (
                        <input
                          type="text"
                          value={String(rule.value?.level ?? rule.value?.education_level ?? '')}
                          onChange={(e) => updatePreselectionRuleValue(index, 'level', e.target.value)}
                          placeholder={t('jobs.educationPlaceholder')}
                          className="w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      )}
                      {(rule.rule_type === 'location' || rule.rule_type === 'custom') && (
                        <input
                          type="text"
                          value={String(rule.value?.location ?? rule.value?.value ?? rule.value?.text ?? '')}
                          onChange={(e) =>
                            updatePreselectionRuleValue(
                              index,
                              rule.rule_type === 'location' ? 'location' : 'value',
                              e.target.value
                            )
                          }
                          placeholder={rule.rule_type === 'location' ? 'Ex : Paris, Dakar' : 'Valeur optionnelle'}
                          className="w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="mb-4 flex flex-wrap gap-4">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-slate-500">{t('jobs.threshold')}</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.5}
                  value={preselectionThreshold}
                  onChange={(e) => setPreselectionThreshold(e.target.value)}
                  className="w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-slate-500">{t('jobs.maxCandidates')}</span>
                <input
                  type="number"
                  min={0}
                  value={preselectionMaxCandidates}
                  onChange={(e) => setPreselectionMaxCandidates(e.target.value)}
                  placeholder="—"
                  className="w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </label>
            </div>
            <button
              type="button"
              onClick={() => savePreselectionMutation.mutate()}
              disabled={savePreselectionMutation.isPending}
              className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            >
              {savePreselectionMutation.isPending ? t('common.loading') : t('jobs.savePreselectionCriteria')}
            </button>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
            <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-800 dark:border-slate-600 dark:text-slate-200">
              {t('jobs.leaderboard')}{' '}
              <span className="ml-2 text-xs font-normal text-slate-500">
                (actualisation 10 s)
              </span>
            </h2>
            <div className="overflow-x-auto">
              {leaderboardLoading ? (
                <div className="flex justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin text-teal-500" />
                </div>
              ) : leaderboard.length === 0 ? (
                <p className="px-4 py-8 text-center text-slate-500">
                  {t('jobs.noLeaderboard')}
                </p>
              ) : (
                <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-600">
                  <thead className="bg-slate-50 dark:bg-slate-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        {t('jobs.rank')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        {t('jobs.name')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        {t('jobs.score')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        {t('jobs.status')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        {t('jobs.badge')}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-600">
                    {(leaderboard as LeaderboardEntry[]).map((entry) => (
                      <tr
                        key={entry.id}
                        className="hover:bg-slate-50 dark:hover:bg-slate-700/50"
                      >
                        <td className="px-4 py-3 text-sm font-medium text-slate-900 dark:text-slate-100">
                          {entry.rank}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-700 dark:text-slate-300">
                          <Link
                            to={`/candidates/${typeof entry.candidate === 'object' ? entry.candidate?.id : entry.candidate}`}
                            className="font-medium text-teal-600 hover:underline dark:text-teal-400"
                          >
                            {getCandidateName(entry.candidate)}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
                          {entry.preselection_score ?? '—'}
                        </td>
                        <td className="px-4 py-3">
                          <span className="rounded bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-600">
                            {getStatusLabel(entry.status, t)}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded px-2 py-0.5 text-xs ${
                              entry.badge === 'manual'
                                ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200'
                                : 'bg-slate-100 text-slate-600 dark:bg-slate-600 dark:text-slate-300'
                            }`}
                          >
                            {entry.badge === 'manual'
                              ? t('jobs.badgeManual')
                              : t('jobs.badgeAuto')}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Table candidats présélectionnés avec actions manuelles */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
            <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-800 dark:border-slate-600 dark:text-slate-200">
              Ajustement manuel
            </h2>
            <div className="overflow-x-auto">
              {preselectedApplications.length === 0 ? (
                <p className="px-4 py-8 text-center text-slate-500">
                  {t('jobs.noLeaderboard')}
                </p>
              ) : (
                <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-600">
                  <thead className="bg-slate-50 dark:bg-slate-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        {t('jobs.name')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        Score
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        {t('jobs.status')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-600">
                    {preselectedApplications.map((app) => (
                      <tr key={app.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/50">
                        <td className="px-4 py-3 text-sm">
                          <Link
                            to={`/candidates/${typeof app.candidate === 'object' ? app.candidate?.id : app.candidate}`}
                            className="font-medium text-teal-600 hover:underline dark:text-teal-400"
                          >
                            {getCandidateName(
                              typeof app.candidate === 'object' ? app.candidate : { first_name: '', last_name: '' }
                            )}
                          </Link>
                          {(app as Application).is_manually_adjusted && (
                            <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800 dark:bg-amber-900/50 dark:text-amber-200">
                              {t('jobs.overrideManual')}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {editScoreAppId === app.id ? (
                            <span className="flex items-center gap-2">
                              <input
                                type="number"
                                step="0.01"
                                value={editScoreValue}
                                onChange={(e) => setEditScoreValue(e.target.value)}
                                className="w-20 rounded border border-slate-300 px-2 py-1 text-sm dark:bg-slate-700 dark:text-slate-100"
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  const v = parseFloat(editScoreValue)
                                  if (!Number.isNaN(v)) {
                                    manualOverrideMutation.mutate({
                                      appId: app.id,
                                      action: 'UPDATE_SCORE',
                                      new_score: v,
                                    })
                                  }
                                }}
                                className="text-xs text-teal-600 hover:underline"
                              >
                                OK
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditScoreAppId(null)}
                                className="text-xs text-slate-500 hover:underline"
                              >
                                {t('common.cancel')}
                              </button>
                            </span>
                          ) : (
                            (app as Application).preselection_score ??
                              (app as Application).selection_score ??
                              '—'
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {forceStatusAppId === app.id ? (
                            <span className="flex items-center gap-2">
                              <select
                                value={forceStatusValue}
                                onChange={(e) => setForceStatusValue(e.target.value)}
                                className="rounded border border-slate-300 px-2 py-1 text-sm dark:bg-slate-700 dark:text-slate-100"
                              >
                                {['preselected', 'shortlisted', 'rejected', 'rejected_preselection', 'rejected_selection'].map((s) => (
                                  <option key={s} value={s}>
                                    {getStatusLabel(s, t)}
                                  </option>
                                ))}
                              </select>
                              <button
                                type="button"
                                onClick={() => {
                                  if (forceStatusValue) {
                                    manualOverrideMutation.mutate({
                                      appId: app.id,
                                      action: 'FORCE_STATUS',
                                      new_status: forceStatusValue,
                                    })
                                  }
                                }}
                                className="text-xs text-teal-600 hover:underline"
                              >
                                OK
                              </button>
                              <button
                                type="button"
                                onClick={() => setForceStatusAppId(null)}
                                className="text-xs text-slate-500 hover:underline"
                              >
                                {t('common.cancel')}
                              </button>
                            </span>
                          ) : (
                            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-600">
                              {getStatusLabel(app.status, t)}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap items-center gap-1">
                            <button
                              type="button"
                              onClick={() =>
                                manualOverrideMutation.mutate({
                                  appId: app.id,
                                  action: 'ADD_TO_SHORTLIST',
                                })
                              }
                              className="rounded p-1.5 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/30"
                              title={t('jobs.addToShortlist')}
                            >
                              <Plus className="h-4 w-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                manualOverrideMutation.mutate({
                                  appId: app.id,
                                  action: 'REMOVE_FROM_SHORTLIST',
                                })
                              }
                              className="rounded p-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30"
                              title={t('jobs.removeFromShortlist')}
                            >
                              <Minus className="h-4 w-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditScoreAppId(app.id)
                                setEditScoreValue(
                                  String(
                                    (app as Application).preselection_score ??
                                      (app as Application).selection_score ??
                                      ''
                                  )
                                )
                              }}
                              className="rounded p-1.5 text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-600"
                              title={t('jobs.editScore')}
                            >
                              <Pencil className="h-4 w-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setForceStatusAppId(app.id)
                                setForceStatusValue(app.status)
                              }}
                              className="rounded p-1.5 text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-600"
                              title={t('jobs.forceStatus')}
                            >
                              <Lock className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Sélection — Critères de sélection (avancés) + Shortlist */}
      {activeTab === 'selection' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
            <h2 className="mb-1 text-base font-semibold text-slate-800 dark:text-slate-200">
              {t('jobs.selectionCriteriaTitle')}
            </h2>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
              {t('jobs.selectionCriteriaHint')}
            </p>

            <div className="mb-6">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                  {t('jobs.selectionScoringRules')}
                </span>
                <button
                  type="button"
                  onClick={addSelectionRule}
                  className="inline-flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
                >
                  <Plus className="h-4 w-4" />
                  {t('jobs.addRule')}
                </button>
              </div>
              {selectionRules.length === 0 ? (
                <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 py-4 text-center text-sm text-slate-500 dark:border-slate-600 dark:bg-slate-800/50 dark:text-slate-400">
                  {t('jobs.selectionNoRulesHint')}
                </p>
              ) : (
                <ul className="space-y-4">
                  {selectionRules.map((rule, index) => (
                    <li
                      key={index}
                      className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-600 dark:bg-slate-800/30"
                    >
                      <div className="mb-3 flex flex-wrap items-center gap-3">
                        <select
                          value={rule.rule_type}
                          onChange={(e) => updateSelectionRule(index, 'rule_type', e.target.value as RuleType)}
                          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        >
                          {RULE_TYPES.map((opt) => (
                            <option key={opt.value} value={opt.value}>{t(`jobs.${opt.labelKey}`)}</option>
                          ))}
                        </select>
                        <label className="flex items-center gap-2">
                          <span className="text-sm text-slate-600 dark:text-slate-300">{t('jobs.points')}</span>
                          <input
                            type="number"
                            min={0}
                            step={1}
                            value={rule.weight}
                            onChange={(e) => updateSelectionRule(index, 'weight', e.target.value)}
                            className="w-20 rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                          />
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={rule.is_required}
                            onChange={(e) => updateSelectionRule(index, 'is_required', e.target.checked)}
                            className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 dark:border-slate-600 dark:bg-slate-700 dark:text-teal-400"
                          />
                          <span className="text-sm text-slate-600 dark:text-slate-300">{t('jobs.required')}</span>
                        </label>
                        <button
                          type="button"
                          onClick={() => removeSelectionRule(index)}
                          className="ml-auto rounded p-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                          title={t('common.delete')}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                      {rule.rule_type === 'keywords' && (
                        <textarea
                          value={String(rule.value?.keywords ?? '')}
                          onChange={(e) => updateSelectionRuleValue(index, 'keywords', e.target.value)}
                          placeholder={t('jobs.keywordsPlaceholder')}
                          rows={3}
                          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:placeholder-slate-400"
                        />
                      )}
                      {rule.rule_type === 'min_experience' && (
                        <input
                          type="number"
                          min={0}
                          value={String(rule.value?.years ?? rule.value?.min_years ?? '')}
                          onChange={(e) => updateSelectionRuleValue(index, 'years', e.target.value)}
                          placeholder={t('jobs.yearsPlaceholder')}
                          className="w-32 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      )}
                      {rule.rule_type === 'education_level' && (
                        <input
                          type="text"
                          value={String(rule.value?.level ?? rule.value?.education_level ?? '')}
                          onChange={(e) => updateSelectionRuleValue(index, 'level', e.target.value)}
                          placeholder={t('jobs.educationPlaceholder')}
                          className="w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      )}
                      {(rule.rule_type === 'location' || rule.rule_type === 'custom') && (
                        <input
                          type="text"
                          value={String(rule.value?.location ?? rule.value?.value ?? rule.value?.text ?? '')}
                          onChange={(e) =>
                            updateSelectionRuleValue(
                              index,
                              rule.rule_type === 'location' ? 'location' : 'value',
                              e.target.value
                            )
                          }
                          placeholder={rule.rule_type === 'location' ? 'Ex : Paris, Dakar' : 'Valeur optionnelle'}
                          className="w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="mb-4">
              <span className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-200">
                {t('jobs.selectionMode')}
              </span>
              <div className="flex flex-wrap gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="selectionMode"
                    checked={selectionModeLocal === 'auto'}
                    onChange={() => setSelectionModeLocal('auto')}
                    className="rounded-full border-slate-300 text-teal-600 focus:ring-teal-500"
                  />
                  {t('jobs.modeAuto')}
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="selectionMode"
                    checked={selectionModeLocal === 'semi_automatic'}
                    onChange={() => setSelectionModeLocal('semi_automatic')}
                    className="rounded-full border-slate-300 text-teal-600 focus:ring-teal-500"
                  />
                  {t('jobs.modeSemi')}
                </label>
              </div>
            </div>
            <div className="mb-4 flex flex-wrap gap-4">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-slate-500">{t('jobs.threshold')}</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.5}
                  value={selectionThreshold}
                  onChange={(e) => setSelectionThreshold(e.target.value)}
                  className="w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-slate-500">{t('jobs.maxCandidates')}</span>
                <input
                  type="number"
                  min={0}
                  value={selectionMaxCandidates}
                  onChange={(e) => setSelectionMaxCandidates(e.target.value)}
                  placeholder="—"
                  className="w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </label>
            </div>
            <button
              type="button"
              onClick={() => saveSelectionMutation.mutate()}
              disabled={saveSelectionMutation.isPending}
              className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            >
              {saveSelectionMutation.isPending ? t('common.loading') : t('jobs.saveSelectionCriteria')}
            </button>
            {selectionMode === 'semi_automatic' && (
              <div className="mt-4">
                <button
                  type="button"
                  onClick={handleGenerateShortlist}
                  disabled={shortlistLoading}
                  className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                >
                  {shortlistLoading ? (
                    <RefreshCw className="h-5 w-5 animate-spin" />
                  ) : null}
                  {t('jobs.generateShortlist')}
                </button>
              </div>
            )}
          </div>
          {(generatedShortlist && generatedShortlist.length > 0) ||
          shortlistedApplications.length > 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
              <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-800 dark:border-slate-600 dark:text-slate-200">
                {t('jobs.shortlistGenerated')}
              </h2>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-600">
                  <thead className="bg-slate-50 dark:bg-slate-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        #
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        {t('jobs.name')}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        Score présélection
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500">
                        Score sélection
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-600">
                    {(generatedShortlist ?? shortlistedApplications).map((entry, idx) => {
                      const isShortlistEntry = 'candidate' in entry && typeof entry.candidate === 'object'
                      const name = isShortlistEntry
                        ? getCandidateName((entry as ShortlistEntry).candidate)
                        : getCandidateName(
                            typeof (entry as Application).candidate === 'object'
                              ? (entry as Application).candidate
                              : { first_name: '', last_name: '' }
                          )
                      const pre = isShortlistEntry
                        ? (entry as ShortlistEntry).preselection_score
                        : (entry as Application).preselection_score
                      const sel = isShortlistEntry
                        ? (entry as ShortlistEntry).selection_score
                        : (entry as Application).selection_score
                      return (
                        <tr key={isShortlistEntry ? (entry as ShortlistEntry).id : (entry as Application).id}>
                          <td className="px-4 py-3 text-sm">{idx + 1}</td>
                          <td className="px-4 py-3 text-sm font-medium text-slate-900 dark:text-slate-100">
                            {name}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
                            {pre ?? '—'}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
                            {sel ?? '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p className="rounded-xl border border-slate-200 bg-white px-4 py-8 text-center text-slate-500 dark:border-slate-700 dark:bg-slate-800/50">
              {t('jobs.noShortlist')}
            </p>
          )}
        </div>
      )}

      {/* Tab: Dashboard KPI */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {kpiLoading ? (
            <div className="flex justify-center py-12">
              <div className="h-10 w-10 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
            </div>
          ) : kpi ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                    <Users className="h-5 w-5" />
                    <span className="text-sm font-medium">{t('jobs.kpiTotalApplications')}</span>
                  </div>
                  <p className="mt-2 text-2xl font-bold text-slate-800 dark:text-slate-100">
                    {(kpi as JobKpi).total_applications}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
                  <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                    <TrendingUp className="h-5 w-5" />
                    <span className="text-sm font-medium">{t('jobs.kpiRejectionRate')}</span>
                  </div>
                  <p className="mt-2 text-2xl font-bold text-slate-800 dark:text-slate-100">
                    {(
                      ((kpi as JobKpi).rejection_rate_preselection ?? 0) +
                      ((kpi as JobKpi).rejection_rate_selection ?? 0)
                    ).toFixed(1)}
                    %
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
                  <span className="text-sm font-medium text-slate-500 dark:text-slate-400">
                    {t('jobs.kpiAvgScore')}
                  </span>
                  <p className="mt-2 text-2xl font-bold text-slate-800 dark:text-slate-100">
                    {(kpi as JobKpi).average_preselection_score ?? '—'}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
                  <span className="text-sm font-medium text-slate-500 dark:text-slate-400">
                    {t('jobs.kpiMaxScore')}
                  </span>
                  <p className="mt-2 text-2xl font-bold text-slate-800 dark:text-slate-100">
                    {(kpi as JobKpi).highest_score ?? '—'}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
                  <span className="text-sm font-medium text-slate-500 dark:text-slate-400">
                    {t('jobs.kpiMinScore')}
                  </span>
                  <p className="mt-2 text-2xl font-bold text-slate-800 dark:text-slate-100">
                    {(kpi as JobKpi).lowest_score ?? '—'}
                  </p>
                </div>
              </div>
              <div className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
                  <h3 className="mb-4 text-sm font-semibold text-slate-800 dark:text-slate-200">
                    {t('jobs.scoreDistribution')}
                  </h3>
                  <div className="space-y-2">
                    {scoreDistribution.length === 0 ? (
                      <p className="text-sm text-slate-500">Aucune donnée</p>
                    ) : (
                      scoreDistribution.map(({ label, count }) => {
                        const max = Math.max(...scoreDistribution.map((d) => d.count), 1)
                        return (
                          <div key={label} className="flex items-center gap-3">
                            <span className="w-16 text-xs text-slate-500">{label}</span>
                            <div className="flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
                              <div
                                className="h-5 rounded-full bg-teal-500 dark:bg-teal-600"
                                style={{ width: `${(count / max) * 100}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
                              {count}
                            </span>
                          </div>
                        )
                      })
                    )}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
                  <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-200">
                    <BarChart3 className="h-4 w-4" />
                    {t('jobs.applicationsEvolution')}
                  </h3>
                  <div className="max-h-48 space-y-1 overflow-y-auto">
                    {applicationsByDate.length === 0 ? (
                      <p className="text-sm text-slate-500">Aucune donnée</p>
                    ) : (
                      applicationsByDate.map(({ date, count }) => (
                        <div
                          key={date}
                          className="flex items-center justify-between rounded px-2 py-1 text-sm hover:bg-slate-50 dark:hover:bg-slate-700/50"
                        >
                          <span className="text-slate-600 dark:text-slate-300">{date}</span>
                          <span className="font-medium text-slate-800 dark:text-slate-100">
                            {count}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <p className="rounded-xl border border-slate-200 bg-white px-4 py-8 text-center text-slate-500 dark:border-slate-700 dark:bg-slate-800/50">
              Aucun KPI disponible.
            </p>
          )}
        </div>
      )}

      {/* Modal clôture offre */}
      {closeModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="close-modal-title"
        >
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl dark:bg-slate-800">
            <h2 id="close-modal-title" className="text-lg font-semibold text-slate-800 dark:text-slate-100">
              {t('jobs.closeConfirmTitle')}
            </h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              {t('jobs.closeConfirmMessage')}
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setCloseModalOpen(false)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={() => closeJobMutation.mutate()}
                disabled={closeJobMutation.isPending}
                className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
              >
                {closeJobMutation.isPending ? t('common.loading') : t('jobs.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
