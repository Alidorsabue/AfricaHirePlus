/**
 * Détail d'une candidature : consultation et édition (notes, statut) sans passer par l'admin Django.
 */
import { useState, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { applicationsApi } from '../api/applications'
import type { Application } from '../types'

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
  const appId = id ? parseInt(id, 10) : 0

  const [notes, setNotes] = useState('')
  const [status, setStatus] = useState('')

  const { data: appRes, isLoading } = useQuery({
    queryKey: ['application', appId],
    queryFn: () => applicationsApi.get(appId),
    enabled: appId > 0,
  })

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Application>) => applicationsApi.update(appId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['application', appId] })
      queryClient.invalidateQueries({ queryKey: ['applications'] })
    },
  })

  const updateStatusMutation = useMutation({
    mutationFn: (newStatus: string) => applicationsApi.updateStatus(appId, newStatus),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['application', appId] })
      queryClient.invalidateQueries({ queryKey: ['applications'] })
    },
  })

  useEffect(() => {
    if (appRes?.data) {
      const a = appRes.data as Application
      setNotes(a.notes ?? '')
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

  const handleSaveNotes = (e: React.FormEvent) => {
    e.preventDefault()
    updateMutation.mutate({ notes })
  }

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newStatus = e.target.value
    setStatus(newStatus)
    updateStatusMutation.mutate(newStatus)
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
                <option value="shortlisted">Shortlisté</option>
                <option value="interview">En entretien</option>
                <option value="offer">Offre envoyée</option>
                <option value="hired">Embauché</option>
                <option value="rejected">Refusé</option>
                <option value="withdrawn">Retirée</option>
              </select>
            </label>
          </div>
        </div>

        {app.cover_letter && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
            <h2 className="font-semibold text-slate-800 dark:text-slate-100">Lettre de motivation</h2>
            <p className="mt-3 whitespace-pre-wrap text-slate-600 dark:text-slate-300">{app.cover_letter}</p>
          </div>
        )}

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          <h2 className="font-semibold text-slate-800 dark:text-slate-100">Notes recruteur</h2>
          <form onSubmit={handleSaveNotes} className="mt-3">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              placeholder="Notes internes sur cette candidature..."
            />
            <button
              type="submit"
              disabled={updateMutation.isPending}
              className="mt-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            >
              {updateMutation.isPending ? t('common.loading') : t('common.save')}
            </button>
          </form>
        </div>

        <div className="text-sm text-slate-500 dark:text-slate-400">
          Score présélection : {app.preselection_score ?? '—'} · Score sélection : {app.selection_score ?? '—'}
        </div>
      </div>
    </div>
  )
}
