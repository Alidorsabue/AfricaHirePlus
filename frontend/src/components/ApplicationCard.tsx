import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { Application } from '../types'

export function ApplicationCard({ application }: { application: Application }) {
  const { t } = useTranslation()
  const candidate = typeof application.candidate === 'object' ? application.candidate : null
  const job = typeof application.job_offer === 'object' ? application.job_offer : null
  const name = candidate
    ? `${candidate.first_name} ${candidate.last_name}`.trim() || candidate.email
    : `#${application.candidate}`
  const title = job?.title ?? `#${application.job_offer}`

  return (
    <div className="text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Link
          to={candidate ? `/candidates/${candidate.id}` : '#'}
          className="font-medium text-teal-600 hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {name}
        </Link>
        <Link
          to={`/applications/${application.id}`}
          className="text-xs text-slate-500 hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {t('common.detail')}
        </Link>
      </div>
      <p className="mt-0.5 text-slate-600 dark:text-slate-400">{title}</p>
      <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
        {new Date(application.applied_at).toLocaleDateString()}
      </p>
    </div>
  )
}
