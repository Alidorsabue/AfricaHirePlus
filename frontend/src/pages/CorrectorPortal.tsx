/**
 * Portail correcteur externe (P8).
 *
 * Flux utilisateur :
 *  1. Le correcteur clique sur le lien magique reçu par email
 *     (`/correct?token=XYZ`).
 *  2. La page valide le token, affiche le contexte (test + scope) puis la
 *     liste des sessions à corriger (anonymisées).
 *  3. Le correcteur ouvre une session ; il voit les questions/réponses et
 *     peut surcharger la note de n'importe quelle réponse, y compris
 *     auto-corrigée.
 *
 * Sécurité côté UI :
 *  - Aucune info identifiante n'est affichée (l'API ne les expose pas).
 *  - Le token est stocké en sessionStorage (volatile).
 *  - Pas d'intercepteur JWT — instance axios dédiée (voir
 *    `frontend/src/api/correctors.ts`).
 */
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useToast } from '../contexts/ToastContext'
import {
  correctorsApi,
  clearCorrectorToken,
  getCorrectorToken,
  setCorrectorToken,
  type CorrectorAnswer,
  type CorrectorSessionDetail,
  type CorrectorSessionListItem,
} from '../api/correctors'

// ===========================================================================
// Composant racine — orchestre auth + navigation interne (liste ↔ détail)
// ===========================================================================
export default function CorrectorPortal() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const tokenFromUrl = searchParams.get('token')
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null)

  // 1) Capture du token : URL > sessionStorage.
  useEffect(() => {
    if (tokenFromUrl) {
      setCorrectorToken(tokenFromUrl)
    }
  }, [tokenFromUrl])

  const hasToken = Boolean(tokenFromUrl || getCorrectorToken())

  // 2) Validation immédiate du token.
  const authQuery = useQuery({
    queryKey: ['corrector', 'auth', tokenFromUrl || getCorrectorToken()],
    queryFn: async () => (await correctorsApi.authCheck()).data,
    enabled: hasToken,
    retry: false,
    staleTime: 60_000,
  })

  if (!hasToken) {
    return <CorrectorMissingToken />
  }
  if (authQuery.isLoading) {
    return <CorrectorLoading label={t('corrector.checkingToken') || 'Vérification du lien...'} />
  }
  if (authQuery.isError || !authQuery.data) {
    return <CorrectorAuthError />
  }

  const auth = authQuery.data

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <CorrectorHeader test={auth.test} scope={auth.corrector.scope} email={auth.corrector.email} />
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
        {activeSessionId ? (
          <CorrectorSessionDetailView
            sessionId={activeSessionId}
            onBack={() => setActiveSessionId(null)}
          />
        ) : (
          <CorrectorSessionListView
            assignedCount={auth.corrector.assigned_count}
            sessionsToReview={auth.sessions_to_review}
            onOpen={setActiveSessionId}
          />
        )}
      </main>
    </div>
  )
}

// ===========================================================================
// Header — Bandeau correcteur avec infos non-identifiantes
// ===========================================================================
function CorrectorHeader({
  test,
  scope,
  email,
}: {
  test: { title: string; job_role: string }
  scope: 'all_candidates' | 'restricted'
  email: string
}) {
  const { t } = useTranslation()
  return (
    <header className="border-b border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-teal-600 dark:text-teal-400">
            {t('corrector.modeLabel') || 'Mode correcteur'}
          </p>
          <h1 className="mt-0.5 text-lg font-semibold text-slate-800 dark:text-slate-100">
            {test.title}
          </h1>
          {test.job_role && (
            <p className="text-sm text-slate-500 dark:text-slate-400">{test.job_role}</p>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-200">
            {email}
          </span>
          <span
            className={`rounded-full px-2.5 py-1 font-medium ${
              scope === 'all_candidates'
                ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200'
                : 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200'
            }`}
          >
            {scope === 'all_candidates'
              ? t('corrector.scopeAll') || 'Tous les candidats'
              : t('corrector.scopeRestricted') || 'Sélection limitée'}
          </span>
          <button
            type="button"
            onClick={() => {
              clearCorrectorToken()
              window.location.href = '/'
            }}
            className="rounded-md border border-slate-300 px-2.5 py-1 font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            {t('corrector.logout') || 'Quitter'}
          </button>
        </div>
      </div>
    </header>
  )
}

// ===========================================================================
// Liste des sessions à corriger
// ===========================================================================
function CorrectorSessionListView({
  assignedCount,
  sessionsToReview,
  onOpen,
}: {
  assignedCount: number | null
  sessionsToReview: number
  onOpen: (id: number) => void
}) {
  const { t } = useTranslation()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['corrector', 'sessions'],
    queryFn: async () => (await correctorsApi.listSessions()).data,
  })

  if (isLoading) {
    return <CorrectorLoading label={t('corrector.loadingSessions') || 'Chargement des sessions...'} />
  }
  if (isError || !data) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-200">
        {t('corrector.errorSessions') || 'Impossible de charger les sessions.'}{' '}
        <button onClick={() => refetch()} className="ml-2 underline">
          {t('common.retry') || 'Réessayer'}
        </button>
      </div>
    )
  }

  const pendingTotal = data.reduce((acc, s) => acc + (s.pending_answers_count || 0), 0)

  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard
          label={t('corrector.statTotalSessions') || 'Sessions à corriger'}
          value={String(data.length)}
        />
        <StatCard
          label={t('corrector.statPendingAnswers') || 'Réponses en attente'}
          value={String(pendingTotal)}
          highlight={pendingTotal > 0}
        />
        <StatCard
          label={
            assignedCount !== null
              ? t('corrector.statAssignedScope') || 'Périmètre attribué'
              : t('corrector.statFullScope') || 'Périmètre'
          }
          value={
            assignedCount !== null
              ? String(assignedCount)
              : t('corrector.allCandidates') || 'Tous'
          }
        />
      </div>

      <h2 className="mt-8 text-sm font-semibold text-slate-700 dark:text-slate-200">
        {t('corrector.sessionsTitle') || 'Sessions des candidats'}{' '}
        <span className="ml-1 text-slate-400">({sessionsToReview})</span>
      </h2>

      {data.length === 0 ? (
        <div className="mt-4 rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-400">
          {t('corrector.noSessions') ||
            "Aucune session à corriger pour l'instant. Revenez plus tard."}
        </div>
      ) : (
        <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500 dark:bg-slate-700/40 dark:text-slate-300">
              <tr>
                <th className="px-4 py-3">{t('corrector.code') || 'Code'}</th>
                <th className="px-4 py-3">{t('corrector.status') || 'Statut'}</th>
                <th className="px-4 py-3">{t('corrector.score') || 'Score'}</th>
                <th className="px-4 py-3">{t('corrector.pending') || 'En attente'}</th>
                <th className="px-4 py-3">{t('corrector.flagged') || 'Suspicion'}</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm dark:divide-slate-700">
              {data.map((s) => (
                <CorrectorSessionRow key={s.id} session={s} onOpen={onOpen} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function CorrectorSessionRow({
  session,
  onOpen,
}: {
  session: CorrectorSessionListItem
  onOpen: (id: number) => void
}) {
  const { t } = useTranslation()
  const pending = session.pending_answers_count || 0
  return (
    <tr className="hover:bg-slate-50/60 dark:hover:bg-slate-700/30">
      <td className="px-4 py-3 font-mono text-xs font-medium text-slate-700 dark:text-slate-200">
        {session.display_code}
      </td>
      <td className="px-4 py-3">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(
            session.status,
          )}`}
        >
          {session.status}
        </span>
      </td>
      <td className="px-4 py-3 text-slate-700 dark:text-slate-200">
        {session.score ?? '—'} / {session.max_score ?? '—'}
        {session.is_passed === true && (
          <span className="ml-2 inline-block rounded bg-emerald-100 px-1.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200">
            OK
          </span>
        )}
        {session.is_passed === false && (
          <span className="ml-2 inline-block rounded bg-rose-100 px-1.5 text-xs font-medium text-rose-700 dark:bg-rose-900/40 dark:text-rose-200">
            KO
          </span>
        )}
      </td>
      <td className="px-4 py-3">
        {pending > 0 ? (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
            {pending}
          </span>
        ) : (
          <span className="text-slate-400">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        {session.is_flagged ? (
          <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-800 dark:bg-rose-900/40 dark:text-rose-200">
            ⚠
          </span>
        ) : (
          <span className="text-slate-400">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        <button
          onClick={() => onOpen(session.id)}
          className="text-sm font-medium text-teal-600 hover:underline dark:text-teal-400"
        >
          {t('corrector.open') || 'Corriger →'}
        </button>
      </td>
    </tr>
  )
}

// ===========================================================================
// Détail d'une session : questions/réponses + override des notes
// ===========================================================================
function CorrectorSessionDetailView({
  sessionId,
  onBack,
}: {
  sessionId: number
  onBack: () => void
}) {
  const { t } = useTranslation()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['corrector', 'session', sessionId],
    queryFn: async () => (await correctorsApi.getSession(sessionId)).data,
  })

  if (isLoading) {
    return <CorrectorLoading label={t('corrector.loadingSession') || 'Chargement de la session...'} />
  }
  if (isError || !data) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-200">
        {t('corrector.errorSession') || 'Impossible de charger la session.'}{' '}
        <button onClick={onBack} className="ml-2 underline">
          {t('common.back') || 'Retour'}
        </button>
      </div>
    )
  }

  return (
    <div>
      <button
        onClick={onBack}
        className="mb-4 text-sm font-medium text-teal-600 hover:underline dark:text-teal-400"
      >
        ← {t('corrector.backToList') || 'Retour à la liste'}
      </button>

      <SessionSummaryCard session={data} />

      <h2 className="mt-8 text-sm font-semibold text-slate-700 dark:text-slate-200">
        {t('corrector.answersTitle') || 'Réponses du candidat'}
      </h2>
      <div className="mt-3 space-y-4">
        {data.answers.map((answer, idx) => (
          <AnswerCard key={answer.id} index={idx + 1} answer={answer} sessionId={sessionId} />
        ))}
      </div>
    </div>
  )
}

function SessionSummaryCard({ session }: { session: CorrectorSessionDetail }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {t('corrector.code') || 'Code candidat'}
          </p>
          <p className="mt-0.5 font-mono text-lg font-semibold text-slate-800 dark:text-slate-100">
            {session.display_code}
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          <KV label={t('corrector.score') || 'Score'} value={`${session.score ?? '—'} / ${session.max_score ?? '—'}`} />
          <KV
            label={t('corrector.pending') || 'En attente'}
            value={String(session.pending_review_points ?? 0)}
          />
          <KV
            label={t('corrector.tabSwitches') || 'Changements onglet'}
            value={String(session.tab_switch_count)}
          />
          <KV
            label={t('corrector.status') || 'Statut'}
            value={
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(session.status)}`}>
                {session.status}
              </span>
            }
          />
        </div>
      </div>
    </div>
  )
}

function AnswerCard({
  index,
  answer,
  sessionId,
}: {
  index: number
  answer: CorrectorAnswer
  sessionId: number
}) {
  const { t } = useTranslation()
  const { toast } = useToast()
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const initialScore = Number(answer.score_obtained ?? 0)
  const [score, setScore] = useState<string>(String(initialScore))
  const [reason, setReason] = useState('')

  const reviewMutation = useMutation({
    mutationFn: async () => {
      const parsed = Number(score)
      if (!Number.isFinite(parsed) || parsed < 0) {
        throw new Error(t('corrector.invalidScore') || 'Note invalide.')
      }
      if (parsed > answer.question_points) {
        throw new Error(
          (t('corrector.scoreTooHigh') || 'La note ne peut pas dépasser') +
            ` ${answer.question_points}`,
        )
      }
      const { data } = await correctorsApi.reviewAnswer(answer.id, {
        score: parsed,
        reason: reason.trim() || undefined,
      })
      return data
    },
    onSuccess: () => {
      toast.success(t('corrector.scoreSaved') || 'Note enregistrée.')
      setEditing(false)
      setReason('')
      qc.invalidateQueries({ queryKey: ['corrector', 'session', sessionId] })
      qc.invalidateQueries({ queryKey: ['corrector', 'sessions'] })
    },
    onError: (e: unknown) => {
      const msg =
        (e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data
          ?.detail || (e as Error)?.message || (t('corrector.errorSave') || 'Erreur')
      toast.error(String(msg))
    },
  })

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase text-slate-500">
            {t('corrector.question') || 'Question'} {index} ·{' '}
            <span className="font-mono">{answer.question_type}</span>
            {answer.question_section_title && (
              <span className="ml-2 text-slate-400">— {answer.question_section_title}</span>
            )}
          </p>
          <h3 className="mt-1 whitespace-pre-wrap text-sm font-medium text-slate-800 dark:text-slate-100">
            {answer.question_text}
          </h3>
        </div>
        <div className="text-right text-sm">
          <p className="text-slate-700 dark:text-slate-200">
            <span className="font-semibold">{answer.score_obtained ?? 0}</span>
            <span className="text-slate-400"> / {answer.question_points}</span>
          </p>
          {answer.pending_manual_review && (
            <p className="mt-0.5 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
              {t('corrector.toReview') || 'À corriger'}
            </p>
          )}
          {answer.is_correct === true && !answer.pending_manual_review && (
            <p className="mt-0.5 inline-block rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200">
              ✓ {t('corrector.correct') || 'Correct'}
            </p>
          )}
        </div>
      </header>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase text-slate-500">
            {t('corrector.candidateResponse') || 'Réponse du candidat'}
          </p>
          <CandidateResponseRenderer answer={answer} />
        </div>
        <div>
          <p className="text-xs font-medium uppercase text-slate-500">
            {t('corrector.expectedAnswer') || 'Réponse attendue'}
          </p>
          <ExpectedAnswerRenderer answer={answer} />
        </div>
      </div>

      <div className="mt-5 border-t border-slate-200 pt-4 dark:border-slate-700">
        {!editing ? (
          <button
            onClick={() => setEditing(true)}
            className="text-sm font-medium text-teal-600 hover:underline dark:text-teal-400"
          >
            {t('corrector.adjustScore') || 'Ajuster la note'}
          </button>
        ) : (
          <div className="space-y-3">
            <div className="flex items-end gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-300">
                  {t('corrector.newScore') || 'Nouvelle note'}{' '}
                  <span className="text-slate-400">/ {answer.question_points}</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min={0}
                  max={answer.question_points}
                  value={score}
                  onChange={(e) => setScore(e.target.value)}
                  className="mt-1 w-32 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-300">
                  {t('corrector.reasonLabel') || 'Justification (optionnelle)'}
                </label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder={t('corrector.reasonPlaceholder') || 'Réponse alternative valide…'}
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => reviewMutation.mutate()}
                disabled={reviewMutation.isPending}
                className="rounded-md bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
              >
                {reviewMutation.isPending
                  ? t('common.saving') || 'Enregistrement...'
                  : t('common.save') || 'Enregistrer'}
              </button>
              <button
                onClick={() => {
                  setEditing(false)
                  setScore(String(initialScore))
                  setReason('')
                }}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
              >
                {t('common.cancel') || 'Annuler'}
              </button>
            </div>
          </div>
        )}
      </div>

      {answer.file_url && (
        <p className="mt-3 text-xs">
          <a
            href={answer.file_url}
            target="_blank"
            rel="noreferrer"
            className="text-teal-600 hover:underline dark:text-teal-400"
          >
            📎 {t('corrector.downloadFile') || 'Télécharger le fichier soumis'}
          </a>
        </p>
      )}
    </article>
  )
}

// ===========================================================================
// Sous-composants utilitaires
// ===========================================================================
function CandidateResponseRenderer({ answer }: { answer: CorrectorAnswer }) {
  const { response, question_type, question_options } = answer
  const empty = (
    <p className="mt-1 text-sm italic text-slate-400">— (vide)</p>
  )
  if (response === null || response === undefined || response === '') return empty

  const opts = Array.isArray(question_options) ? question_options : []

  if (question_type === 'mcq' || question_type === 'qcm') {
    const selected = toArray(response)
    if (selected.length === 0) return empty
    return (
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-slate-700 dark:text-slate-200">
        {selected.map((idx) => (
          <li key={String(idx)}>{opts[Number(idx)]?.label ?? `Option ${idx}`}</li>
        ))}
      </ul>
    )
  }
  if (question_type === 'true_false') {
    return (
      <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">
        {String(response) === 'true' ? '✓ Vrai' : '✗ Faux'}
      </p>
    )
  }
  if (question_type === 'numeric') {
    return (
      <p className="mt-1 text-sm font-mono text-slate-700 dark:text-slate-200">
        {String(response)}
      </p>
    )
  }
  return (
    <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm text-slate-700 dark:bg-slate-700/40 dark:text-slate-200">
      {typeof response === 'string' ? response : JSON.stringify(response, null, 2)}
    </pre>
  )
}

function ExpectedAnswerRenderer({ answer }: { answer: CorrectorAnswer }) {
  const { question_correct_answer, question_type, question_options } = answer
  if (question_correct_answer === null || question_correct_answer === undefined) {
    return (
      <p className="mt-1 text-sm italic text-slate-400">
        (libre · à évaluer manuellement)
      </p>
    )
  }
  const opts = Array.isArray(question_options) ? question_options : []
  if (question_type === 'mcq' || question_type === 'qcm') {
    const correct = toArray(question_correct_answer)
    return (
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-slate-700 dark:text-slate-200">
        {correct.map((idx) => (
          <li key={String(idx)}>{opts[Number(idx)]?.label ?? `Option ${idx}`}</li>
        ))}
      </ul>
    )
  }
  return (
    <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm text-slate-700 dark:bg-slate-700/40 dark:text-slate-200">
      {typeof question_correct_answer === 'string'
        ? question_correct_answer
        : JSON.stringify(question_correct_answer, null, 2)}
    </pre>
  )
}

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string
  value: string
  highlight?: boolean
}) {
  return (
    <div
      className={`rounded-xl border bg-white p-4 shadow-sm dark:bg-slate-800 ${
        highlight
          ? 'border-amber-300 ring-1 ring-amber-200 dark:border-amber-700 dark:ring-amber-900/40'
          : 'border-slate-200 dark:border-slate-700'
      }`}
    >
      <p className="text-xs font-medium uppercase text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-800 dark:text-slate-100">{value}</p>
    </div>
  )
}

function KV({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-slate-800 dark:text-slate-100">{value}</p>
    </div>
  )
}

function CorrectorMissingToken() {
  const { t } = useTranslation()
  return (
    <CorrectorErrorScreen
      title={t('corrector.missingTokenTitle') || 'Lien invalide'}
      message={
        t('corrector.missingTokenMsg') ||
        "Aucun token correcteur détecté. Ouvrez le lien reçu dans votre email."
      }
    />
  )
}

function CorrectorAuthError() {
  const { t } = useTranslation()
  return (
    <CorrectorErrorScreen
      title={t('corrector.invalidTokenTitle') || 'Lien expiré ou révoqué'}
      message={
        t('corrector.invalidTokenMsg') ||
        "Ce lien de correction n'est plus valide. Contactez le recruteur pour en recevoir un nouveau."
      }
      onClear={() => {
        clearCorrectorToken()
        window.location.search = ''
      }}
    />
  )
}

function CorrectorErrorScreen({
  title,
  message,
  onClear,
}: {
  title: string
  message: string
  onClear?: () => void
}) {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6 dark:bg-slate-900">
      <div className="max-w-md rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-2xl text-rose-600 dark:bg-rose-900/40 dark:text-rose-300">
          ⚠
        </div>
        <h1 className="text-lg font-semibold text-slate-800 dark:text-slate-100">{title}</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{message}</p>
        {onClear && (
          <button
            onClick={onClear}
            className="mt-4 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            {t('common.dismiss') || 'Fermer'}
          </button>
        )}
      </div>
    </div>
  )
}

function CorrectorLoading({ label }: { label: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
      <div className="text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">{label}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function toArray(v: unknown): unknown[] {
  if (Array.isArray(v)) return v
  if (v === null || v === undefined) return []
  return [v]
}

function statusBadgeClass(status: string): string {
  const s = (status || '').toUpperCase()
  if (s === 'COMPLETED' || s === 'SUBMITTED')
    return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200'
  if (s === 'IN_PROGRESS')
    return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200'
  if (s === 'EXPIRED')
    return 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-200'
  return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
}
