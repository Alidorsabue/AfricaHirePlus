import { useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { testsApi } from '../api/tests'

export default function TestResultDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const resultId = id ? Number(id) : 0

  const { data, isLoading } = useQuery({
    queryKey: ['testResultReport', resultId],
    queryFn: async () => {
      const res = await testsApi.results.report(resultId)
      return res.data as any
    },
    enabled: resultId > 0,
  })

  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
      </div>
    )
  }

  const report = data.report || {}
  const sections = report.sections || {}
  const competencies = report.competencies || {}
  const questions = report.questions || {}

  return (
    <div>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
          {t('test.resultDetail') || 'Détail du test candidat'}
        </h1>
        <Link
          to="/tests/results"
          className="text-sm font-medium text-teal-600 hover:underline dark:text-teal-400"
        >
          ← {t('test.results')}
        </Link>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <p className="text-xs font-medium uppercase text-slate-500">Score global</p>
          <p className="mt-2 text-2xl font-semibold text-slate-800 dark:text-slate-100">
            {report.score_total} / {report.max_score}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <p className="text-xs font-medium uppercase text-slate-500">Tab switches</p>
          <p className="mt-2 text-2xl font-semibold text-slate-800 dark:text-slate-100">
            {data.tab_switch_count}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <p className="text-xs font-medium uppercase text-slate-500">Suspicion</p>
          <p className="mt-2 text-lg font-semibold text-slate-800 dark:text-slate-100">
            {data.is_flagged ? 'Flagged' : 'Normal'}
          </p>
        </div>
      </div>

      <div className="mt-8 grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <h2 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
            Score par section
          </h2>
          {Object.keys(sections).length === 0 ? (
            <p className="text-sm text-slate-500">Aucune section définie.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {Object.entries(sections).map(([key, val]: any) => (
                <li key={key} className="flex items-center justify-between">
                  <span>{val.title}</span>
                  <span className="font-medium">
                    {val.score} / {val.max_score}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <h2 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
            Score par compétence
          </h2>
          {Object.keys(competencies).length === 0 ? (
            <p className="text-sm text-slate-500">Aucune compétence renseignée.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {Object.entries(competencies).map(([key, val]: any) => (
                <li key={key} className="flex items-center justify-between">
                  <span>{val.name}</span>
                  <span className="font-medium">
                    {val.score} / {val.max_score}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="mt-8 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
        <h2 className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
          Réponses détaillées
        </h2>
        <div className="space-y-3 text-sm">
          {Object.entries(questions).map(([qid, q]: any, index) => (
            <div
              key={qid}
              className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 dark:border-slate-700 dark:bg-slate-800/40"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">
                  Question {index + 1}
                </span>
                <span className="text-xs">
                  {q.points} / {q.max}{' '}
                  {q.pending_manual_review ? '(à corriger manuellement)' : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

