import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { jobsApi } from '../api/jobs'
import { unwrapList } from '../api/utils'
import type { Application, LeaderboardEntry } from '../types'

function getCandidateName(
  candidate: LeaderboardEntry['candidate'] | Application['candidate']
): string {
  if (typeof candidate === 'number') return '—'
  const first = candidate?.first_name ?? ''
  const last = candidate?.last_name ?? ''
  return [first, last].filter(Boolean).join(' ') || (candidate as { email?: string })?.email || '—'
}

export default function ShortlistRanking() {
  const { t } = useTranslation()
  const [jobId, setJobId] = useState<number | ''>('')

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => unwrapList((await jobsApi.list()).data),
  })

  const selectedId = typeof jobId === 'number' ? jobId : 0

  const { data: leaderboard = [], isLoading } = useQuery({
    queryKey: ['leaderboard', selectedId],
    queryFn: async () => {
      const { data } = await jobsApi.getLeaderboard(selectedId)
      return Array.isArray(data) ? data : unwrapList(data)
    },
    enabled: selectedId > 0,
  })

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        {t('nav.shortlist')}
      </h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{t('shortlist.subtitle')}</p>

      <div className="mt-6 max-w-md">
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
          {t('shortlist.selectJob')}
        </label>
        <select
          value={jobId}
          onChange={(e) => setJobId(e.target.value ? Number(e.target.value) : '')}
          className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-4 py-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        >
          <option value="">{t('shortlist.chooseJob')}</option>
          {jobs.map((j) => (
            <option key={j.id} value={j.id}>
              {j.title}
            </option>
          ))}
        </select>
      </div>

      {selectedId > 0 && (
        <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          {isLoading ? (
            <p className="p-8 text-center text-slate-500">{t('common.loading')}</p>
          ) : leaderboard.length === 0 ? (
            <p className="p-8 text-center text-slate-500">{t('shortlist.empty')}</p>
          ) : (
            <ol className="divide-y divide-slate-100 dark:divide-slate-700">
              {(leaderboard as LeaderboardEntry[]).map((entry) => {
                const candidateId =
                  typeof entry.candidate === 'object' ? entry.candidate?.id : entry.candidate
                return (
                  <li
                    key={entry.id}
                    className="flex items-center gap-4 px-4 py-3 sm:px-6"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                      {entry.rank}
                    </span>
                    <div className="min-w-0 flex-1">
                      <Link
                        to={candidateId ? `/candidates/${candidateId}` : '#'}
                        className="font-medium text-slate-800 hover:text-teal-600 dark:text-slate-100 dark:hover:text-teal-400"
                      >
                        {getCandidateName(entry.candidate)}
                      </Link>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {t(`pipeline.${entry.status}` as 'pipeline.applied', {
                          defaultValue: entry.status,
                        })}
                      </p>
                    </div>
                    <span className="shrink-0 text-lg font-semibold tabular-nums text-teal-600 dark:text-teal-400">
                      {entry.preselection_score != null
                        ? Number(entry.preselection_score).toFixed(0)
                        : '—'}
                    </span>
                    <Link
                      to={`/applications/${entry.id}`}
                      className="shrink-0 text-sm text-teal-600 hover:underline dark:text-teal-400"
                    >
                      {t('common.detail')}
                    </Link>
                  </li>
                )
              })}
            </ol>
          )}
          {selectedId > 0 && (
            <div className="border-t border-slate-200 px-4 py-3 dark:border-slate-700">
              <Link
                to={`/jobs/${selectedId}`}
                className="text-sm font-medium text-teal-600 hover:underline dark:text-teal-400"
              >
                {t('shortlist.manageOnJob')}
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
