import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, Play, Plus, Pencil, List, Code, FileUp, ClipboardList } from 'lucide-react'
import { testsApi } from '../api/tests'
import { applicationsApi } from '../api/applications'
import { unwrapList } from '../api/utils'

/** Affiche un résumé des types de questions (QCM, code, fichier) pour rendre les évolutions visibles. */
function QuestionTypeBadges({ questions }: { questions?: Array<{ question_type?: string }> }) {
  if (!questions?.length) return null
  const types = new Set(questions.map((q) => q.question_type))
  const labels: { key: string; icon: React.ReactNode }[] = []
  if (types.has('single_choice') || types.has('multiple_choice') || types.has('qcm_single') || types.has('qcm_multi')) labels.push({ key: 'QCM', icon: <ClipboardList className="h-3 w-3" /> })
  if (types.has('code')) labels.push({ key: 'Code', icon: <Code className="h-3 w-3" /> })
  if (types.has('file_upload')) labels.push({ key: 'Fichier', icon: <FileUp className="h-3 w-3" /> })
  if (types.has('text') || types.has('open_text')) labels.push({ key: 'Texte', icon: null })
  if (types.has('number') || types.has('numeric')) labels.push({ key: 'Numérique', icon: null })
  if (labels.length === 0) return null
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {labels.map(({ key, icon }) => (
        <span key={key} className="inline-flex items-center gap-1 rounded bg-teal-100 px-1.5 py-0.5 text-xs font-medium text-teal-800 dark:bg-teal-900/50 dark:text-teal-200">
          {icon}
          {key}
        </span>
      ))}
    </div>
  )
}

function downloadBlob(blob: Blob, filename: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function Tests() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const applicationId = searchParams.get('applicationId')

  const deleteMutation = useMutation({
    mutationFn: (id: number) => testsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tests'] }),
  })

  const { data: tests = [], isLoading } = useQuery({
    queryKey: ['tests'],
    queryFn: async () => unwrapList((await testsApi.list()).data),
  })

  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: async () => unwrapList((await applicationsApi.list()).data),
  })

  const handleExportResultsExcel = async () => {
    try {
      const { data } = await testsApi.exportResultsExcel()
      downloadBlob(data as Blob, 'resultats_tests.xlsx')
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
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">{t('test.technicalTest')}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/tests/results"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            <List className="h-4 w-4" />
            {t('test.results')}
          </Link>
          <button
            type="button"
            onClick={handleExportResultsExcel}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            <Download className="h-4 w-4" />
            {t('test.exportResultsExcel')}
          </button>
          <Link
            to="/tests/new"
            className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
          >
            <Plus className="h-4 w-4" />
            {t('test.newTest')}
          </Link>
        </div>
      </div>

      <p className="mt-4 text-sm text-slate-600 dark:text-slate-400">
        {t('test.introCapabilities') || 'Les tests peuvent inclure des QCM, questions à rédaction, questions de code (éditeur intégré) et téléversement de fichiers (Excel, Word, PDF, PowerPoint, PBIX). Chronomètre, une seule tentative par candidat et indicateurs anti-triche.'}
      </p>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
          Candidature (pour passer un test)
        </label>
        <select
          value={applicationId ?? ''}
          onChange={(e) => {
            const v = e.target.value
            if (v) setSearchParams({ applicationId: v })
            else setSearchParams({})
          }}
          className="mt-1 w-full max-w-md rounded-lg border border-slate-300 px-4 py-2 focus:border-teal-500 focus:outline-none"
        >
          <option value="">— Choisir une candidature —</option>
          {applications.map((app) => {
            const cand = typeof app.candidate === 'object' ? app.candidate : null
            const job = typeof app.job_offer === 'object' ? app.job_offer : null
            const name = cand ? `${cand.first_name} ${cand.last_name}`.trim() || cand.email : `#${app.candidate}`
            const title = job?.title ?? ''
            return (
              <option key={app.id} value={app.id}>
                {name} – {title}
              </option>
            )
          })}
        </select>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tests.map((test) => (
          <div
            key={test.id}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800/50"
          >
            <h2 className="font-semibold text-slate-800 dark:text-slate-100">{test.title}</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{test.description || ''}</p>
            <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
              {test.duration_minutes ?? 0} min · {(test.questions?.length ?? 0)} {t('test.question')}(s)
            </p>
            <QuestionTypeBadges questions={test.questions} />
            {(test.questions?.length ?? 0) === 0 && (
              <p className="mt-2 rounded-lg bg-amber-50 py-2 px-3 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                {t('test.noQuestionsHint') || 'Aucune question. Cliquez sur Modifier pour ajouter des questions (QCM, code, téléversement de fichier…).'}
              </p>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              <Link
                to={`/tests/${test.id}/edit`}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
              >
                <Pencil className="h-4 w-4" />
                {t('common.edit')}
              </Link>
              <button
                type="button"
                onClick={() => window.confirm(t('common.delete')) && deleteMutation.mutate(test.id)}
                className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/20"
              >
                {t('common.delete')}
              </button>
              <Link
                to={`/tests/${test.id}?applicationId=${applicationId || ''}`}
                className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                style={{ pointerEvents: !applicationId ? 'none' : undefined }}
                title={!applicationId ? 'Choisir une candidature ci-dessus' : undefined}
              >
                <Play className="h-4 w-4" />
                Passer le test
              </Link>
            </div>
          </div>
        ))}
      </div>
      {tests.length === 0 && (
        <p className="mt-6 text-center text-slate-500">Aucun test configuré.</p>
      )}
    </div>
  )
}
