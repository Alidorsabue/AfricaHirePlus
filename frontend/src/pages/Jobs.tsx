import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Plus, Pencil, Download, ExternalLink } from 'lucide-react'
import { jobsApi } from '../api/jobs'
import { unwrapList } from '../api/utils'

const statusKeys: Record<string, string> = {
  draft: 'jobs.draft',
  published: 'jobs.published',
  closed: 'jobs.closed',
  archived: 'jobs.archived',
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function Jobs() {
  const { t } = useTranslation()
  const [statusFilter, setStatusFilter] = useState<string>('')

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs', statusFilter],
    queryFn: async () => unwrapList((await jobsApi.list(statusFilter ? { status: statusFilter } : undefined)).data),
  })

  const exportExcel = async () => {
    try {
      const { data } = await jobsApi.exportExcel()
      downloadBlob(data as Blob, 'offres.xlsx')
    } catch {
      // ignore
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
      </div>
    )
  }

  return (
    <div>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-slate-800">{t('jobs.title')}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          >
            <option value="">Tous les statuts</option>
            {Object.entries(statusKeys).map(([value, key]) => (
              <option key={value} value={value}>{t(key)}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={exportExcel}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-4 w-4" />
            {t('jobs.exportExcel')}
          </button>
          <Link
            to="/jobs/new"
            className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
          >
            <Plus className="h-4 w-4" />
            {t('jobs.new')}
          </Link>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm">
        {jobs.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-500">
            {t('jobs.noJobs')}
            <Link to="/jobs/new" className="ml-2 font-medium text-teal-600 hover:underline">
              {t('jobs.new')}
            </Link>
          </div>
        ) : (
          <ul className="divide-y divide-slate-200">
            {jobs.map((job) => (
              <li
                key={job.id}
                className="flex flex-col gap-2 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <Link
                    to={`/jobs/${job.id}`}
                    className="font-medium text-teal-600 hover:underline"
                  >
                    {job.title}
                  </Link>
                  <div className="mt-1 flex flex-wrap gap-2 text-sm text-slate-500">
                    <span>{job.location || '—'}</span>
                    <span>·</span>
                    <span>{t(`jobs.${job.contract_type || 'other'}`)}</span>
                    <span>·</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5">{t(statusKeys[job.status] || 'jobs.draft')}</span>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {job.status === 'published' && job.slug && (
                    <a
                      href={`/offres/${job.slug}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-lg border border-teal-200 bg-teal-50 px-3 py-1.5 text-sm text-teal-700 hover:bg-teal-100 dark:border-teal-700 dark:bg-teal-900/30 dark:text-teal-300 dark:hover:bg-teal-900/50"
                    >
                      <ExternalLink className="h-4 w-4" />
                      {t('jobs.viewOffer')}
                    </a>
                  )}
                  <Link
                    to={`/jobs/${job.id}/edit`}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
                  >
                    <Pencil className="h-4 w-4" />
                    {t('jobs.edit')}
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
