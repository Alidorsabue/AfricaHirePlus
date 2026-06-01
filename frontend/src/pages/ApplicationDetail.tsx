/**
 * Détail d'une candidature : consultation et édition (notes, statut) sans passer par l'admin Django.
 */
import { useState, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { applicationsApi } from '../api/applications'
import { unwrapList } from '../api/utils'
import type { Application, ApplicationAuditLog, ApplicationNote } from '../types'
import { useToast } from '../contexts/ToastContext'

function getCandidateName(app: Application): string {
  const c = typeof app.candidate === 'object' ? app.candidate : null
  if (!c) return '—'
  return [c.first_name, c.last_name].filter(Boolean).join(' ') || (c as { email?: string }).email || '—'
}

function getJobTitle(app: Application): string {
  const j = typeof app.job_offer === 'object' ? app.job_offer : null
  return j?.title ?? '—'
}

export default function ApplicationDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const appId = id ? parseInt(id, 10) : 0

  const [status, setStatus] = useState('')
  const [newNote, setNewNote] = useState('')
  const [pinNote, setPinNote] = useState(false)
  const [statusReason, setStatusReason] = useState('')

  const { data: appRes, isLoading } = useQuery({
    queryKey: ['application', appId],
    queryFn: () => applicationsApi.get(appId),
    enabled: appId > 0,
  })

  const { data: notesRes } = useQuery({
    queryKey: ['application', appId, 'notes'],
    queryFn: async () => (await applicationsApi.notes.list(appId)).data,
    enabled: appId > 0,
  })

  const { data: auditRes } = useQuery({
    queryKey: ['application', appId, 'audit'],
    queryFn: async () => (await applicationsApi.audit.list(appId)).data,
    enabled: appId > 0,
  })

  const updateStatusMutation = useMutation({
    mutationFn: (payload: { newStatus: string; reason?: string }) =>
      applicationsApi.updateStatus(appId, payload.newStatus, payload.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['application', appId] })
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      queryClient.invalidateQueries({ queryKey: ['application', appId, 'audit'] })
      toast.success(t('common.saved') || 'Enregistré.')
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: { details?: Record<string, string[]>; message?: string } } } })
        ?.response?.data?.error?.message
      toast.error(msg || t('common.error') || 'Erreur')
    },
  })

  const createNoteMutation = useMutation({
    mutationFn: (payload: { body: string; is_pinned?: boolean }) =>
      applicationsApi.notes.create(appId, payload),
    onSuccess: () => {
      setNewNote('')
      setPinNote(false)
      queryClient.invalidateQueries({ queryKey: ['application', appId, 'notes'] })
      queryClient.invalidateQueries({ queryKey: ['application', appId, 'audit'] })
      toast.success(t('common.saved') || 'Enregistré.')
    },
    onError: () => toast.error(t('common.error') || 'Erreur'),
  })

  const deleteNoteMutation = useMutation({
    mutationFn: (noteId: number) => applicationsApi.notes.delete(noteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['application', appId, 'notes'] })
      toast.success(t('common.deleted') || 'Supprimé.')
    },
    onError: () => toast.error(t('common.error') || 'Erreur'),
  })

  useEffect(() => {
    if (appRes?.data) {
      const a = appRes.data as Application
      setStatus(a.status ?? '')
    }
  }, [appRes?.data])

  if (!appId || isLoading || !appRes?.data) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
      </div>
    )
  }

  const app = appRes.data as Application
  const notes = unwrapList(notesRes) as ApplicationNote[]
  const audit = unwrapList(auditRes) as ApplicationAuditLog[]

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newStatus = e.target.value
    setStatus(newStatus)
    updateStatusMutation.mutate({ newStatus, reason: statusReason || undefined })
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link to="/pipeline" className="text-sm font-medium text-teal-600 hover:underline">
          ← {t('common.back')}
        </Link>
      </div>

      <div className="mt-6 space-y-6">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {getCandidateName(app)} – {getJobTitle(app)}
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Candidature #{app.id} · {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : '—'}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
              {t('jobs.status')}
              <select
                value={status}
                onChange={handleStatusChange}
                disabled={updateStatusMutation.isPending}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              >
                <option value="applied">Postulé</option>
                <option value="preselected">Pré-sélectionné</option>
                <option value="rejected_preselection">Refusé (présélection)</option>
                <option value="shortlisted">Shortlisté</option>
                <option value="rejected_selection">Refusé (sélection)</option>
                <option value="interview">En entretien</option>
                <option value="offer">Offre envoyée</option>
                <option value="hired">Embauché</option>
                <option value="rejected">Refusé</option>
                <option value="withdrawn">Retirée</option>
              </select>
            </label>
            <input
              value={statusReason}
              onChange={(e) => setStatusReason(e.target.value)}
              placeholder={t('applications.statusReason') || 'Motif (optionnel)'}
              className="min-w-[220px] flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
        </div>

        {app.cover_letter && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
            <h2 className="font-semibold text-slate-800 dark:text-slate-100">Lettre de motivation</h2>
            <p className="mt-3 whitespace-pre-wrap text-slate-600 dark:text-slate-300">{app.cover_letter}</p>
          </div>
        )}

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold text-slate-800 dark:text-slate-100">
              {t('applications.internalNotes') || 'Notes internes'}
            </h2>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!newNote.trim()) return
              createNoteMutation.mutate({ body: newNote, is_pinned: pinNote })
            }}
            className="mt-3"
          >
            <textarea
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              placeholder={t('applications.addNotePlaceholder') || 'Ajouter une note interne…'}
            />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <label className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={pinNote}
                  onChange={(e) => setPinNote(e.target.checked)}
                />
                {t('applications.pinNote') || 'Épingler'}
              </label>
              <button
                type="submit"
                disabled={createNoteMutation.isPending}
                className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
              >
                {createNoteMutation.isPending ? (t('common.loading') || '...') : (t('common.add') || 'Ajouter')}
              </button>
            </div>
          </form>

          <ul className="mt-4 space-y-2">
            {notes.length === 0 ? (
              <li className="text-sm text-slate-500 dark:text-slate-400">
                {t('applications.noNotes') || 'Aucune note.'}
              </li>
            ) : (
              notes
                .slice()
                .sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned) || (b.created_at || '').localeCompare(a.created_at || ''))
                .map((n) => (
                  <li key={n.id} className="rounded-lg border border-slate-200 p-3 dark:border-slate-600">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          {n.is_pinned && (
                            <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                              {t('applications.pinned') || 'Épinglée'}
                            </span>
                          )}
                          <span className="text-xs text-slate-500 dark:text-slate-400">
                            {n.author_name || n.author_email || '—'} · {n.created_at ? new Date(n.created_at).toLocaleString() : '—'}
                          </span>
                        </div>
                        <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-200">
                          {n.body}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          const ok = window.confirm(t('common.confirmDelete') || 'Supprimer cette note ?')
                          if (!ok) return
                          deleteNoteMutation.mutate(n.id)
                        }}
                        disabled={deleteNoteMutation.isPending}
                        className="rounded border border-red-200 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900/50 dark:text-red-300 dark:hover:bg-red-900/20"
                      >
                        {t('common.delete') || 'Supprimer'}
                      </button>
                    </div>
                  </li>
                ))
            )}
          </ul>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <h2 className="font-semibold text-slate-800 dark:text-slate-100">
            {t('applications.auditLog') || 'Journal d’audit'}
          </h2>
          <ul className="mt-3 space-y-2">
            {audit.length === 0 ? (
              <li className="text-sm text-slate-500 dark:text-slate-400">
                {t('applications.noAudit') || 'Aucun évènement.'}
              </li>
            ) : (
              audit.slice(0, 30).map((e) => (
                <li key={e.id} className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-600">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-medium text-slate-800 dark:text-slate-100">
                      {e.action_label || e.action}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {(e.actor_name || 'Système')}{e.ip_address ? ` · ${e.ip_address}` : ''}
                  </div>
                  {e.reason ? (
                    <div className="mt-2 whitespace-pre-wrap text-slate-700 dark:text-slate-200">{e.reason}</div>
                  ) : null}
                </li>
              ))
            )}
          </ul>
        </div>

        <div className="text-sm text-slate-500 dark:text-slate-400">
          Score présélection : {app.preselection_score ?? '—'} · Score sélection : {app.selection_score ?? '—'}
        </div>
      </div>
    </div>
  )
}
