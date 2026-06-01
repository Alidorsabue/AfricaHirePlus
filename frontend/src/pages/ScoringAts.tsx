import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, RefreshCw } from 'lucide-react'
import { jobsApi } from '../api/jobs'
import { applicationsApi } from '../api/applications'
import { unwrapList } from '../api/utils'

export default function ScoringAts() {
  const { t } = useTranslation()
  const { data: jobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => unwrapList((await jobsApi.list()).data),
  })
  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: async () => unwrapList((await applicationsApi.list()).data),
  })

  const published = jobs.filter((j) => j.status === 'published')

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        {t('nav.scoringAts')}
      </h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{t('scoringAts.subtitle')}</p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {jobsLoading ? (
          <p className="col-span-full text-slate-500">{t('common.loading')}</p>
        ) : published.length === 0 ? (
          <p className="col-span-full text-slate-500">{t('scoringAts.noJobs')}</p>
        ) : (
          published.map((job) => {
            const jobApps = applications.filter((a) => {
              const jid = typeof a.job_offer === 'object' ? a.job_offer?.id : a.job_offer
              return jid === job.id
            })
            const withScore = jobApps.filter((a) => a.preselection_score != null).length
            return (
              <div
                key={job.id}
                className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800/50"
              >
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-teal-100 p-2 dark:bg-teal-900/40">
                    <BarChart3 className="h-5 w-5 text-teal-700 dark:text-teal-300" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h2 className="font-semibold text-slate-800 dark:text-slate-100">{job.title}</h2>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                      {t('scoringAts.candidatesScored', {
                        scored: withScore,
                        total: jobApps.length,
                      })}
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    to={`/jobs/${job.id}`}
                    className="inline-flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
                  >
                    {t('scoringAts.openJob')}
                  </Link>
                  <Link
                    to={`/jobs/${job.id}`}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
                  >
                    <RefreshCw className="h-4 w-4" />
                    {t('scoringAts.criteria')}
                  </Link>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
