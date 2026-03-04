import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { jobsApi } from '../api/jobs'
import { unwrapList } from '../api/utils'
import type { PublicJobOffer } from '../api/jobs'

export default function OffresCandidat() {
  const { t } = useTranslation()
  const { data: rawData, isLoading } = useQuery({
    queryKey: ['jobs', 'public'],
    queryFn: async () => (await jobsApi.listPublic()).data,
  })
  const jobs = unwrapList(rawData) as PublicJobOffer[]

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
        {t('candidat.browseJobs')}
      </h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        {t('candidat.browseJobsHint')}
      </p>

      {jobs.length === 0 ? (
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-8 text-center dark:border-slate-600 dark:bg-slate-800">
          <p className="text-slate-600 dark:text-slate-300">{t('candidat.noOffers')}</p>
        </div>
      ) : (
        <ul className="mt-6 space-y-3">
          {jobs.map((job) => (
            <li
              key={job.id}
              className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-600 dark:bg-slate-800"
            >
              <Link
                to={`/offres/${job.slug}`}
                className="block font-semibold text-slate-800 hover:text-teal-600 dark:text-slate-100 dark:hover:text-teal-400"
              >
                {job.title}
              </Link>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {job.location} · {job.contract_type}
              </p>
              <Link
                to={`/offres/${job.slug}/postuler`}
                className="mt-2 inline-block text-sm font-medium text-teal-600 hover:underline dark:text-teal-400"
              >
                {t('candidat.apply')}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
