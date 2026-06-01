import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { applicationsApi } from '../api/applications'
import { unwrapList } from '../api/utils'
import type { Application } from '../types'

function candidateName(app: Application): string {
  const c = typeof app.candidate === 'object' ? app.candidate : null
  if (!c) return '—'
  return [c.first_name, c.last_name].filter(Boolean).join(' ') || c.email || '—'
}

function jobTitle(app: Application): string {
  const j = typeof app.job_offer === 'object' ? app.job_offer : null
  return j?.title ?? '—'
}

export default function ApplicationsList() {
  const { t } = useTranslation()
  const { data: applications = [], isLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: async () => unwrapList((await applicationsApi.list()).data),
  })

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        {t('nav.applications')}
      </h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        {t('applicationsList.subtitle')}
      </p>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
        {isLoading ? (
          <p className="p-8 text-center text-slate-500">{t('common.loading')}</p>
        ) : applications.length === 0 ? (
          <p className="p-8 text-center text-slate-500">{t('applicationsList.empty')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-400">
                  <th className="px-4 py-3 font-medium">{t('applicationsList.candidate')}</th>
                  <th className="px-4 py-3 font-medium">{t('applicationsList.job')}</th>
                  <th className="px-4 py-3 font-medium">{t('applicationsList.status')}</th>
                  <th className="px-4 py-3 font-medium">{t('applicationsList.score')}</th>
                  <th className="px-4 py-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr
                    key={app.id}
                    className="border-b border-slate-100 last:border-0 dark:border-slate-700/80"
                  >
                    <td className="px-4 py-3 font-medium text-slate-800 dark:text-slate-100">
                      {candidateName(app)}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{jobTitle(app)}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                        {t(`pipeline.${app.status}` as 'pipeline.applied', { defaultValue: app.status })}
                      </span>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-slate-600 dark:text-slate-400">
                      {app.preselection_score != null
                        ? Number(app.preselection_score).toFixed(0)
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={`/applications/${app.id}`}
                        className="text-sm font-medium text-teal-600 hover:underline dark:text-teal-400"
                      >
                        {t('common.detail')}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
