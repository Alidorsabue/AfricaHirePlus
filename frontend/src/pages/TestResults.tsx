/**
 * Liste des résultats aux tests (équivalent admin CandidateTestResult).
 */
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { testsApi } from '../api/tests'
import { applicationsApi } from '../api/applications'
import { unwrapList } from '../api/utils'

export default function TestResults() {
  const { t } = useTranslation()

  const { data: resultsData, isLoading } = useQuery({
    queryKey: ['testResults'],
    queryFn: () => testsApi.results.list(),
  })

  const results = unwrapList(resultsData?.data ?? [])

  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: async () => unwrapList((await applicationsApi.list()).data),
  })

  const getApplicationLabel = (appId: number) => {
    const app = applications.find((a) => a.id === appId)
    if (!app) return `#${appId}`
    const cand = typeof app.candidate === 'object' ? app.candidate : null
    const job = typeof app.job_offer === 'object' ? app.job_offer : null
    const name = cand ? `${cand.first_name} ${cand.last_name}`.trim() || cand.email : `#${app.candidate}`
    return `${name} – ${job?.title ?? ''}`
  }

  const toNum = (v: string | number | null | undefined) =>
    typeof v === 'number' ? v : v != null ? Number(v) : 0
  const avgScore =
    results.length > 0
      ? results.reduce((acc, r) => acc + toNum(r.score), 0) / results.length
      : 0

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
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
          {t('test.results')}
        </h1>
        <Link
          to="/tests"
          className="text-sm font-medium text-teal-600 hover:underline dark:text-teal-400"
        >
          ← {t('test.technicalTest')}
        </Link>
      </div>

      {results.length > 0 && (
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
            <p className="text-xs font-medium uppercase text-slate-500">Candidats</p>
            <p className="mt-2 text-2xl font-semibold text-slate-800 dark:text-slate-100">
              {results.length}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
            <p className="text-xs font-medium uppercase text-slate-500">Score moyen</p>
            <p className="mt-2 text-2xl font-semibold text-slate-800 dark:text-slate-100">
              {avgScore.toFixed(1)}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
            <p className="text-xs font-medium uppercase text-slate-500">Flagged</p>
            <p className="mt-2 text-2xl font-semibold text-slate-800 dark:text-slate-100">
              {results.filter((r) => r.is_flagged === true).length}
            </p>
          </div>
        </div>
      )}

      <div className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
        {results.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-500 dark:text-slate-400">
            Aucun résultat pour le moment.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-600">
              <thead className="bg-slate-50 dark:bg-slate-800">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
                    Candidature
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
                    Test
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
                    Statut
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
                    Score
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
                    Tab switches
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
                    Temps passé
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-slate-500 dark:text-slate-400">
                    Détail
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-600">
                {results
                  .slice()
                  .sort((a, b) => toNum(b.score) - toNum(a.score))
                  .map((r) => {
                    const started = r.started_at ? new Date(r.started_at).getTime() : null
                    const submitted = r.submitted_at ? new Date(r.submitted_at).getTime() : null
                    const durationMinutes =
                      started && submitted ? Math.max(0, (submitted - started) / 60000) : null
                    return (
                      <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/50">
                        <td className="px-4 py-3 text-sm text-slate-700 dark:text-slate-300">
                          {getApplicationLabel(
                            typeof r.application === 'object'
                              ? (r.application as { id: number }).id
                              : r.application,
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-700 dark:text-slate-300">
                          {typeof r.test === 'object' ? (r.test as { title: string }).title : `#${r.test}`}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded px-2 py-0.5 text-xs ${
                              r.is_flagged === true
                                ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-200'
                                : 'bg-slate-100 text-slate-700 dark:bg-slate-600 dark:text-slate-100'
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-700 dark:text-slate-300">
                          {r.score != null && r.max_score != null ? `${r.score} / ${r.max_score}` : '—'}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-700 dark:text-slate-300">
                          {r.tab_switch_count != null ? r.tab_switch_count : '—'}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-700 dark:text-slate-300">
                          {durationMinutes != null ? `${durationMinutes.toFixed(1)} min` : '—'}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <Link
                            to={`/tests/results/${r.id}`}
                            className="text-teal-600 hover:underline dark:text-teal-400"
                          >
                            Voir
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
