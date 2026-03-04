import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { FileText, X } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { jobsApi } from '../api/jobs'
import type { JobOffer } from '../types'

function getApiErrorMessage(error: unknown): string {
  if (isAxiosError(error) && error.response?.data != null) {
    const d = error.response.data
    if (typeof d === 'string') return d
    if (typeof d === 'object' && !Array.isArray(d)) {
      const parts = Object.entries(d).map(([k, v]) =>
        Array.isArray(v) ? `${k}: ${v.join(' ')}` : `${k}: ${String(v)}`
      )
      return parts.join(' — ')
    }
  }
  return error instanceof Error ? error.message : String(error)
}

const CONTRACT_TYPES = ['cdi', 'cdd', 'freelance', 'internship', 'part_time', 'other'] as const
const STATUSES = ['draft', 'published', 'closed', 'archived'] as const
const ACCEPT_DOC = '.pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export default function JobForm() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const isNew = !id
  const queryClient = useQueryClient()
  const { user } = useAuth()

  const [form, setForm] = useState({
    title: '',
    description: '',
    requirements: '',
    benefits: '',
    location: '',
    country: '',
    contract_type: 'cdi',
    status: 'draft',
    salary_min: '' as string | number,
    salary_max: '' as string | number,
    salary_currency: 'XOF',
    salary_visible: false,
    published_at: '',
    deadline: '',
  })
  const [documentFile, setDocumentFile] = useState<File | null>(null)
  const [existingDocumentUrl, setExistingDocumentUrl] = useState<string | null>(null)

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', id],
    queryFn: () => jobsApi.get(Number(id)),
    enabled: !isNew && !!id,
  })

  /** Format ISO ou datetime pour input datetime-local (YYYY-MM-DDTHH:mm) */
  const toDatetimeLocal = (s: string | null | undefined): string => {
    if (!s) return ''
    const d = new Date(s)
    if (Number.isNaN(d.getTime())) return ''
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    return `${y}-${m}-${day}T${h}:${min}`
  }

  useEffect(() => {
    if (job?.data) {
      const j = job.data as JobOffer
      setForm({
        title: j.title ?? '',
        description: j.description ?? '',
        requirements: j.requirements ?? '',
        benefits: j.benefits ?? '',
        location: j.location ?? '',
        country: j.country ?? '',
        contract_type: j.contract_type ?? 'cdi',
        status: j.status ?? 'draft',
        salary_min: j.salary_min ?? '',
        salary_max: j.salary_max ?? '',
        salary_currency: j.salary_currency ?? 'XOF',
        salary_visible: j.salary_visible ?? false,
        published_at: toDatetimeLocal(j.published_at),
        deadline: toDatetimeLocal(j.deadline),
      })
      setExistingDocumentUrl(j.description_document_url ?? null)
    }
  }, [job?.data])

  const createMutation = useMutation({
    mutationFn: (data: Partial<JobOffer> | FormData) => jobsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      navigate('/jobs')
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: Partial<JobOffer> | FormData) => jobsApi.update(Number(id), data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['job', id] })
      navigate('/jobs')
    },
  })

  const hasDocument = Boolean(documentFile || existingDocumentUrl)
  const descriptionRequired = !hasDocument

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value, type } = e.target
    const checked = (e.target as HTMLInputElement).checked
    setForm((p) => ({
      ...p,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  const buildFormData = (): FormData => {
    const fd = new FormData()
    fd.append('title', form.title)
    fd.append('description', form.description)
    fd.append('requirements', form.requirements)
    fd.append('benefits', form.benefits)
    fd.append('location', form.location)
    fd.append('country', form.country)
    fd.append('contract_type', form.contract_type)
    fd.append('status', form.status)
    fd.append('salary_currency', form.salary_currency)
    fd.append('salary_visible', String(form.salary_visible))
    if (form.salary_min !== '') fd.append('salary_min', String(form.salary_min))
    if (form.salary_max !== '') fd.append('salary_max', String(form.salary_max))
    if (form.published_at) fd.append('published_at', new Date(form.published_at).toISOString())
    if (form.deadline) fd.append('deadline', new Date(form.deadline).toISOString())
    if (documentFile) fd.append('description_document', documentFile)
    return fd
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (descriptionRequired && !form.description.trim()) {
      return
    }
    if (documentFile) {
      const fd = buildFormData()
      if (isNew && user?.company != null) {
        fd.append('company', String(Number(user.company)))
        createMutation.mutate(fd)
      } else if (!isNew) {
        updateMutation.mutate(fd)
      }
      return
    }
    const payload = {
      ...form,
      salary_min: form.salary_min === '' ? null : Number(form.salary_min),
      salary_max: form.salary_max === '' ? null : Number(form.salary_max),
      published_at: form.published_at ? new Date(form.published_at).toISOString() : null,
      deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
    }
    if (isNew && user?.company != null) {
      createMutation.mutate({ ...payload, company: Number(user.company) })
    } else if (!isNew) {
      updateMutation.mutate(payload)
    }
  }

  if (!isNew && isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent dark:border-teal-400" />
      </div>
    )
  }

  const mutating = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        {isNew ? t('jobs.new') : t('jobs.edit')}
      </h1>
      <form onSubmit={handleSubmit} className="mt-6 space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800 dark:shadow-slate-900/50">
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
            {getApiErrorMessage(error)}
          </div>
        )}
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('jobs.title')} *</label>
            <input
              name="title"
              value={form.title}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:placeholder-slate-400"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('jobs.status')}</label>
            <select
              name="status"
              value={form.status}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>{t(`jobs.${s}`)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('jobs.contractType')}</label>
            <select
              name="contract_type"
              value={form.contract_type}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              {CONTRACT_TYPES.map((c) => (
                <option key={c} value={c}>{t(`jobs.${c}`)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('jobs.location')}</label>
            <input
              name="location"
              value={form.location}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 placeholder-slate-500 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:placeholder-slate-400"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Pays</label>
            <input
              name="country"
              value={form.country}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 placeholder-slate-500 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:placeholder-slate-400"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('jobs.publishedAt')}</label>
            <input
              type="datetime-local"
              name="published_at"
              value={form.published_at}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('jobs.publishedAtHint')}</p>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('jobs.deadline')}</label>
            <input
              type="datetime-local"
              name="deadline"
              value={form.deadline}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('jobs.deadlineHint')}</p>
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
            {t('jobs.description')} {descriptionRequired ? '*' : ''}
          </label>
          <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
            {t('jobs.descriptionOrDocument')}
          </p>
          <textarea
            name="description"
            value={form.description}
            onChange={handleChange}
            rows={4}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:placeholder-slate-400"
            required={descriptionRequired}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
            {t('jobs.importDocument')}
          </label>
          <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
            {t('jobs.importDocumentHint')}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600">
              <FileText className="h-4 w-4" />
              <input
                type="file"
                accept={ACCEPT_DOC}
                className="hidden"
                onChange={(e) => setDocumentFile(e.target.files?.[0] ?? null)}
              />
              {documentFile ? documentFile.name : t('jobs.chooseFile')}
            </label>
            {existingDocumentUrl && !documentFile && (
              <a
                href={existingDocumentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-teal-600 hover:underline dark:text-teal-400 dark:hover:text-teal-300"
              >
                {t('jobs.viewDocument')}
              </a>
            )}
            {documentFile && (
              <button
                type="button"
                onClick={() => setDocumentFile(null)}
                className="rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-600 dark:hover:text-slate-200"
                title={t('common.cancel')}
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('jobs.requirements')}</label>
          <textarea
            name="requirements"
            value={form.requirements}
            onChange={handleChange}
            rows={3}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 placeholder-slate-500 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:placeholder-slate-400"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('jobs.benefits')}</label>
          <textarea
            name="benefits"
            value={form.benefits}
            onChange={handleChange}
            rows={2}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 placeholder-slate-500 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:placeholder-slate-400"
          />
        </div>

        <div className="flex gap-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              name="salary_visible"
              checked={form.salary_visible}
              onChange={handleChange}
              className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 dark:border-slate-600 dark:bg-slate-700 dark:text-teal-400"
            />
            <span className="text-sm text-slate-700 dark:text-slate-200">Salaire visible</span>
          </label>
        </div>
        <div className="flex gap-4">
          <button
            type="submit"
            disabled={mutating}
            className="rounded-lg bg-teal-600 px-6 py-2.5 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
          >
            {mutating ? t('common.loading') : t('jobs.save')}
          </button>
          <button
            type="button"
            onClick={() => navigate('/jobs')}
            className="rounded-lg border border-slate-300 px-6 py-2.5 font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            {t('common.cancel')}
          </button>
        </div>
      </form>
    </div>
  )
}
