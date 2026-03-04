import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Clock, ChevronRight, ChevronLeft, Send, Flag } from 'lucide-react'
import { testsApi } from '../api/tests'
import type { Question } from '../types'

export default function TechnicalTest() {
  const { t } = useTranslation()
  const { testId } = useParams<{ testId: string }>()
  const [searchParams] = useSearchParams()
  const applicationId = searchParams.get('applicationId')
  const queryClient = useQueryClient()

  const [started, setStarted] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string | string[]>>({})
  const [secondsLeft, setSecondsLeft] = useState(0)
  const [submitted, setSubmitted] = useState(false)
  const [markedForReview, setMarkedForReview] = useState<Set<number>>(new Set())
  const [sessionStarting, setSessionStarting] = useState(false)
  const autosaveTimer = useRef<number | null>(null)

  const { data: testData, isLoading } = useQuery({
    queryKey: ['test', testId],
    queryFn: () => testsApi.get(Number(testId)),
    enabled: !!testId,
  })

  const submitMutation = useMutation({
    mutationFn: () =>
      testsApi.submitAnswers(
        Number(applicationId),
        Number(testId),
        answers as Record<string, unknown>
      ),
    onSuccess: () => {
      setSubmitted(true)
      queryClient.invalidateQueries({ queryKey: ['tests'] })
      queryClient.invalidateQueries({ queryKey: ['testResults'] })
    },
  })

  const test = testData?.data
  const durationMinutes = test?.duration_minutes ?? 60

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const handleStartSession = useCallback(async () => {
    if (!applicationId || !testId) return
    setSessionStarting(true)
    try {
      const { data } = await testsApi.startSession(Number(applicationId), Number(testId))
      const remaining = typeof data.seconds_left === 'number' ? data.seconds_left : durationMinutes * 60
      setSecondsLeft(remaining)
      setStarted(true)
    } finally {
      setSessionStarting(false)
    }
  }, [applicationId, testId, durationMinutes])

  // Timer countdown (basé sur secondsLeft calculé côté backend)
  useEffect(() => {
    if (!started || submitted) return
    const interval = window.setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          window.clearInterval(interval)
          if (!submitMutation.isPending) {
            submitMutation.mutate()
          }
          return 0
        }
        return s - 1
      })
    }, 1000)
    return () => window.clearInterval(interval)
  }, [started, submitted, submitMutation.isPending])

  // Auto-save toutes les 10 secondes
  useEffect(() => {
    if (!started || submitted || !applicationId || !testId) return
    if (autosaveTimer.current) {
      window.clearInterval(autosaveTimer.current)
    }
    autosaveTimer.current = window.setInterval(() => {
      testsApi.autoSave(Number(applicationId), Number(testId), answers as Record<string, unknown>).catch(() => {
        // en cas d'erreur, on ignore pour ne pas bloquer l'UX
      })
    }, 10000)
    return () => {
      if (autosaveTimer.current) {
        window.clearInterval(autosaveTimer.current)
      }
    }
  }, [started, submitted, applicationId, testId, answers])

  // Anti-triche : détection changement d'onglet + désactivation clic droit / copier-coller
  useEffect(() => {
    if (!applicationId || !testId) return

    const handleVisibility = () => {
      if (document.visibilityState === 'hidden') {
        testsApi.tabSwitch(Number(applicationId), Number(testId)).catch(() => {
          // silencieux
        })
      }
    }

    const preventDefault = (e: Event) => {
      e.preventDefault()
    }

    document.addEventListener('visibilitychange', handleVisibility)
    document.addEventListener('contextmenu', preventDefault)
    document.addEventListener('copy', preventDefault)
    document.addEventListener('cut', preventDefault)
    document.addEventListener('paste', preventDefault)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility)
      document.removeEventListener('contextmenu', preventDefault)
      document.removeEventListener('copy', preventDefault)
      document.removeEventListener('cut', preventDefault)
      document.removeEventListener('paste', preventDefault)
    }
  }, [applicationId, testId])

  if (isLoading || !test) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
      </div>
    )
  }

  const questions = (test.questions ?? []) as Question[]
  const currentQuestion = questions[currentIndex]

  if (submitted) {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-lg">
        <h1 className="text-2xl font-bold text-slate-800">{t('test.timeUp')}</h1>
        <p className="mt-4 text-slate-600">
          {t('test.thankYou') || 'Merci, votre test a bien été soumis. Les résultats seront communiqués par le recruteur.'}
        </p>
      </div>
    )
  }

  if (!started) {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-slate-200 bg-white p-8 shadow-lg">
        <h1 className="text-2xl font-bold text-slate-800">{test.title}</h1>
        <p className="mt-2 text-slate-600">{test.description || ''}</p>
        <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-slate-600">
          <li>Le test est chronométré : {durationMinutes} {t('test.minutes')}.</li>
          <li>Une seule tentative est autorisée par candidat.</li>
          <li>Évitez de changer d&apos;onglet pendant le test (anti-triche).</li>
          <li>Vos réponses sont enregistrées automatiquement toutes les 10 secondes.</li>
        </ul>
        <p className="mt-3 text-sm text-slate-500">
          {questions.length} {t('test.question')}(s)
        </p>
        <button
          type="button"
          onClick={() => {
            if (window.confirm(t('test.confirmStart') || 'Démarrer le test maintenant ?')) {
              void handleStartSession()
            }
          }}
          disabled={sessionStarting || !applicationId}
          className="mt-8 w-full rounded-lg bg-teal-600 py-3 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {sessionStarting ? t('common.loading') : t('test.start')}
        </button>
      </div>
    )
  }

  if (questions.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-slate-500">
        Aucune question dans ce test.
      </div>
    )
  }

  const setAnswer = (qId: number, value: string | string[]) => {
    setAnswers((p) => ({ ...p, [qId]: value }))
  }

  const toggleMarkForReview = (qId: number) => {
    setMarkedForReview((prev) => {
      const next = new Set(prev)
      if (next.has(qId)) next.delete(qId)
      else next.add(qId)
      return next
    })
  }

  const handleSubmit = () => {
    if (window.confirm(t('test.confirmSubmit'))) {
      submitMutation.mutate()
    }
  }

  const progress = questions.length ? ((currentIndex + 1) / questions.length) * 100 : 0
  const isMarked = currentQuestion && markedForReview.has(currentQuestion.id as number)

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-2 font-medium text-slate-700">
            <Clock className="h-5 w-5 text-amber-500" />
            {t('test.remaining')}: {formatTime(secondsLeft)}
          </span>
          <span className="text-sm text-slate-500">
            {t('test.question')} {currentIndex + 1} {t('test.of')} {questions.length}
          </span>
        </div>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-teal-500 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-medium text-slate-800">{currentQuestion.text}</h2>
          <button
            type="button"
            onClick={() => toggleMarkForReview(currentQuestion.id as number)}
            className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs font-medium ${
              isMarked
                ? 'border-amber-500 bg-amber-50 text-amber-700'
                : 'border-slate-300 text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Flag className="h-3 w-3" />
            {isMarked ? 'Marked' : 'Mark for review'}
          </button>
        </div>
        <div className="mt-4">
          {currentQuestion.question_type === 'single_choice' && currentQuestion.options?.length && (
            <ul className="space-y-2">
              {currentQuestion.options.map((opt: { id: string; label: string }) => (
                <li key={opt.id}>
                  <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 py-2 px-3 hover:bg-slate-50">
                    <input
                      type="radio"
                      name={`q-${currentQuestion.id}`}
                      checked={answers[currentQuestion.id] === opt.id}
                      onChange={() => setAnswer(currentQuestion.id, opt.id)}
                      className="text-teal-600"
                    />
                    <span>{opt.label}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          {currentQuestion.question_type === 'multiple_choice' && currentQuestion.options?.length && (
            <ul className="space-y-2">
              {currentQuestion.options.map((opt: { id: string; label: string }) => {
                const current = (answers[currentQuestion.id] as string[]) ?? []
                const checked = current.includes(opt.id)
                return (
                  <li key={opt.id}>
                    <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 py-2 px-3 hover:bg-slate-50">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          const next = checked
                            ? current.filter((x) => x !== opt.id)
                            : [...current, opt.id]
                          setAnswer(currentQuestion.id, next)
                        }}
                        className="rounded text-teal-600"
                      />
                      <span>{opt.label}</span>
                    </label>
                  </li>
                )
              })}
            </ul>
          )}
          {(currentQuestion.question_type === 'text' || currentQuestion.question_type === 'number') && (
            <textarea
              rows={4}
              maxLength={2000}
              value={(answers[currentQuestion.id] as string) ?? ''}
              onChange={(e) => setAnswer(currentQuestion.id, e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
            />
          )}
          {currentQuestion.question_type === 'code' && (
            <div className="space-y-2">
              {currentQuestion.code_language && (
                <p className="text-xs font-medium uppercase text-slate-500">
                  Langage attendu : {currentQuestion.code_language}
                </p>
              )}
              {currentQuestion.starter_code && (
                <pre className="max-h-40 overflow-auto rounded-lg bg-slate-900/90 p-3 text-xs text-slate-50">
                  <code>{currentQuestion.starter_code}</code>
                </pre>
              )}
              <textarea
                rows={10}
                value={(answers[currentQuestion.id] as string) ?? ''}
                onChange={(e) => setAnswer(currentQuestion.id, e.target.value)}
                placeholder="Écrivez votre code ici..."
                className="w-full rounded-lg border border-slate-300 bg-slate-950/95 px-4 py-2.5 font-mono text-sm text-slate-50 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
              />
            </div>
          )}
          {currentQuestion.question_type === 'file_upload' && (
            <div className="space-y-3">
              {currentQuestion.attachment && (
                <a
                  href={currentQuestion.attachment as unknown as string}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center text-sm font-medium text-teal-600 hover:underline"
                >
                  Télécharger l’énoncé / template
                </a>
              )}
              <div>
                <label className="text-sm font-medium text-slate-700">
                  Importer votre fichier (Excel, Word, PDF, PowerPoint, PBIX)
                </label>
                <input
                  type="file"
                  accept=".xlsx,.xls,.doc,.docx,.pdf,.ppt,.pptx,.pbix"
                  className="mt-1 block w-full text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-teal-600 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-teal-700"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file && applicationId && testId) {
                      void testsApi
                        .uploadFile(Number(applicationId), Number(testId), currentQuestion.id as number, file)
                        .catch(() => {
                          // silencieux pour le candidat
                        })
                    }
                  }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
          disabled={currentIndex === 0}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          <ChevronLeft className="h-4 w-4" />
          {t('test.previous')}
        </button>
        {currentIndex < questions.length - 1 ? (
          <button
            type="button"
            onClick={() => setCurrentIndex((i) => i + 1)}
            className="inline-flex items-center gap-1 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
          >
            {t('test.next')}
            <ChevronRight className="h-4 w-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitMutation.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            {t('test.submit')}
          </button>
        )}
      </div>
    </div>
  )
}
