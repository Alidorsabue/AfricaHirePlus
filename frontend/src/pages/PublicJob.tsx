import { useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, FileText, ExternalLink } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { jobsApi } from '../api/jobs'

const CONTRACT_KEYS: Record<string, string> = {
  cdi: 'jobs.cdi',
  cdd: 'jobs.cdd',
  freelance: 'jobs.freelance',
  internship: 'jobs.internship',
  part_time: 'jobs.partTime',
  other: 'jobs.other',
}

export default function PublicJob() {
  const { slug } = useParams<{ slug: string }>()
  const { t } = useTranslation()
  const { user } = useAuth()

  const { data: jobRes, isLoading, error } = useQuery({
    queryKey: ['publicJob', slug],
    queryFn: () => jobsApi.getPublicBySlug(slug!),
    enabled: !!slug && !!user,
  })

  const job = jobRes?.data
  const offerUrl = slug ? `/offres/${slug}` : ''
  const isExpired = Boolean(
    job?.deadline && new Date(job.deadline).getTime() < Date.now()
  )

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
              to={offerUrl ? `/login?next=${encodeURIComponent(offerUrl)}` : '/login'}
              className="inline-flex justify-center rounded-lg bg-teal-600 px-4 py-2.5 font-medium text-white hover:bg-teal-700"
            >
              {t('nav.login')}
            </Link>
            <Link
              to={offerUrl ? `/register/candidate?next=${encodeURIComponent(offerUrl)}` : '/register/candidate'}
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
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Link
          to="/candidat"
          className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-teal-600 hover:text-teal-700 dark:text-teal-400"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('publicJob.backToCandidatePage')}
        </Link>
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <div className="border-b border-slate-200 p-6 dark:border-slate-700">
            <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">{job.title}</h1>
            <div className="mt-2 flex flex-wrap gap-2 text-sm text-slate-600 dark:text-slate-400">
              {job.location && <span>{job.location}</span>}
              {job.country && (
                <>
                  {job.location && <span>·</span>}
                  <span>{job.country}</span>
                </>
              )}
              <span>·</span>
              <span>{t(CONTRACT_KEYS[job.contract_type] || 'jobs.other')}</span>
            </div>
            {job.salary_visible && (job.salary_min != null || job.salary_max != null) && (
              <p className="mt-1 text-sm font-medium text-teal-600 dark:text-teal-400">
                {job.salary_min != null && job.salary_max != null
                  ? `${job.salary_min} – ${job.salary_max} ${job.salary_currency}`
                  : job.salary_min != null
                    ? `À partir de ${job.salary_min} ${job.salary_currency}`
                    : `Jusqu'à ${job.salary_max} ${job.salary_currency}`}
              </p>
            )}
          </div>

          <div className="space-y-6 p-6">
            {job.description && (
              <section>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  {t('jobs.description')}
                </h2>
                <div className="mt-2 whitespace-pre-wrap text-slate-700 dark:text-slate-300">
                  {job.description}
                </div>
              </section>
            )}
            {job.description_document_url && (
              <section>
                <a
                  href={job.description_document_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-teal-500 bg-teal-50 px-4 py-2 text-teal-700 hover:bg-teal-100 dark:border-teal-400 dark:bg-teal-900/30 dark:text-teal-300 dark:hover:bg-teal-900/50"
                >
                  <FileText className="h-4 w-4" />
                  {t('jobs.viewDocument')}
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </section>
            )}
            {job.requirements && (
              <section>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  {t('jobs.requirements')}
                </h2>
                <div className="mt-2 whitespace-pre-wrap text-slate-700 dark:text-slate-300">
                  {job.requirements}
                </div>
              </section>
            )}
            {job.benefits && (
              <section>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  {t('jobs.benefits')}
                </h2>
                <div className="mt-2 whitespace-pre-wrap text-slate-700 dark:text-slate-300">
                  {job.benefits}
                </div>
              </section>
            )}

            {isExpired ? (
              <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-700 dark:bg-amber-900/30">
                <p className="font-medium text-amber-800 dark:text-amber-200">
                  {t('publicJob.offerExpired')}
                </p>
                <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
                  {t('publicJob.offerExpiredHint')}
                </p>
              </div>
            ) : (
              <div className="pt-4">
                <Link
                  to={`/offres/${slug}/postuler`}
                  className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 font-medium text-white hover:bg-teal-700"
                >
                  {t('publicJob.applyButton')}
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
