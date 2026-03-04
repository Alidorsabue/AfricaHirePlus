import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Briefcase, ClipboardList, Play } from 'lucide-react'
import { applicationsApi } from '../api/applications'
import { testsApi } from '../api/tests'
import { unwrapList } from '../api/utils'
import type { Application } from '../types'

const STATUS_KEYS: Record<string, string> = {
  applied: 'pipeline.applied',
  preselected: 'pipeline.preselected',
  rejected_preselection: 'pipeline.rejected_preselection',
  shortlisted: 'pipeline.shortlisted',
  rejected_selection: 'pipeline.rejected_selection',
  interview: 'pipeline.interview',
  offer: 'pipeline.offer',
  hired: 'pipeline.hired',
  rejected: 'pipeline.rejected',
  withdrawn: 'pipeline.withdrawn',
}

function getStatusLabel(status: string, t: (k: string) => string): string {
  const key = STATUS_KEYS[status] ?? `pipeline.${status}`
  const out = t(key)
  return out !== key ? out : status
}

export default function MesCandidatures() {
  const { t } = useTranslation()
  const { data: rawData, isLoading } = useQuery({
    queryKey: ['applications', 'mine'],
    queryFn: async () => (await applicationsApi.mine()).data,
  })
  const { data: availableTestsData, isLoading: loadingTests } = useQuery({
    queryKey: ['tests', 'available-for-candidate'],
    queryFn: async () => (await testsApi.availableForCandidate()).data,
  })
  const applications = unwrapList(rawData) as Application[]
  const availableTests = Array.isArray(availableTestsData) ? availableTestsData : []

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent dark:border-teal-400" />
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        {t('candidat.mesCandidatures')}
      </h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        {t('candidat.mesCandidaturesHint')}
      </p>

      {!loadingTests && availableTests.length > 0 && (
        <div className="mt-6 rounded-xl border border-teal-200 bg-teal-50/50 p-4 dark:border-teal-800 dark:bg-teal-900/20">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-800 dark:text-slate-100">
            <ClipboardList className="h-5 w-5 text-teal-600 dark:text-teal-400" />
            {t('candidat.testsToTake') || 'Tests à passer'}
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            {t('candidat.testsToTakeHint') || 'Passez les tests techniques liés à vos candidatures. Une seule tentative par test.'}
          </p>
          <ul className="mt-4 space-y-3">
            {availableTests.map((item) => (
              <li
                key={`${item.application_id}-${item.test_id}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-600 dark:bg-slate-800/50"
              >
                <div>
                  <span className="font-medium text-slate-800 dark:text-slate-100">{item.test_title}</span>
                  <span className="ml-2 text-sm text-slate-500 dark:text-slate-400">
                    — {item.job_title || t('candidat.application')} {item.duration_minutes != null ? `· ${item.duration_minutes} min` : ''}
                  </span>
                </div>
                {item.is_completed ? (
                  <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600 dark:bg-slate-600 dark:text-slate-200">
                    {t('candidat.testCompleted') || 'Terminé'}
                  </span>
                ) : (
                  <Link
                    to={`/candidat/tests/${item.test_id}?applicationId=${item.application_id}`}
                    className="inline-flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
                  >
                    <Play className="h-4 w-4" />
                    {t('candidat.takeTest') || 'Passer le test'}
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {applications.length === 0 ? (
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-8 text-center dark:border-slate-600 dark:bg-slate-800">
          <Briefcase className="mx-auto h-12 w-12 text-slate-400 dark:text-slate-500" />
          <p className="mt-4 text-slate-600 dark:text-slate-300">
            {t('candidat.noApplications')}
          </p>
          <Link
            to="/candidat/offres"
            className="mt-4 inline-block rounded-lg bg-teal-600 px-4 py-2 font-medium text-white hover:bg-teal-700"
          >
            {t('candidat.browseJobs')}
          </Link>
        </div>
      ) : (
        <ul className="mt-6 space-y-3">
          {applications.map((app) => {
            const job = typeof app.job_offer === 'object' ? app.job_offer : null
            const jobTitle = job?.title ?? `#${typeof app.job_offer === 'object' ? (app.job_offer as { id?: number }).id : app.job_offer}`
            const slug = job?.slug
            return (
              <li
                key={app.id}
                className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-600 dark:bg-slate-800"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <h2 className="font-semibold text-slate-800 dark:text-slate-100">
                      {jobTitle}
                    </h2>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <span
                        className="inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-600 dark:text-slate-200"
                        title={t('jobs.status')}
                      >
                        {getStatusLabel(app.status, t)}
                      </span>
                      <span className="text-sm text-slate-500 dark:text-slate-400">
                        {app.applied_at
                          ? new Date(app.applied_at).toLocaleDateString()
                          : '—'}
                      </span>
                    </div>
                  </div>
                  {slug && (
                    <Link
                      to={`/offres/${slug}`}
                      className="shrink-0 text-sm font-medium text-teal-600 hover:underline dark:text-teal-400"
                    >
                      {t('candidat.viewOffer')}
                    </Link>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
