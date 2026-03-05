import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  DndContext,
  type DragEndEvent,
  type DragStartEvent,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { Download } from 'lucide-react'
import { applicationsApi } from '../api/applications'
import { jobsApi } from '../api/jobs'
import { unwrapList } from '../api/utils'
import type { Application, ApplicationStatus } from '../types'
import { PipelineColumn } from '../components/PipelineColumn'
import { ApplicationCard } from '../components/ApplicationCard'

const STATUSES: ApplicationStatus[] = [
  'applied',
  'preselected',
  'rejected_preselection',
  'shortlisted',
  'rejected_selection',
  'interview',
  'offer',
  'hired',
  'rejected',
  'withdrawn',
]

const statusLabelKeys: Record<ApplicationStatus, string> = {
  applied: 'pipeline.applied',
  preselected: 'pipeline.preselected',
  rejected_preselection: 'pipeline.rejected_preselection',
  shortlisted: 'pipeline.shortlisted',
  rejected_selection: 'pipeline.rejected_selection',
  interview: 'pipeline.interview',
  offer: 'pipeline.offer',
  hired: 'pipeline.hired',
  rejected: 'pipeline.rejected',
  withdrawn: 'pipeline.withdrawn',
}

function downloadBlob(blob: Blob, filename: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function Pipeline() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [jobFilter, setJobFilter] = useState<number | ''>('')
  const [activeId, setActiveId] = useState<number | null>(null)

  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: async () => unwrapList((await applicationsApi.list()).data),
  })

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => unwrapList((await jobsApi.list()).data),
  })

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      applicationsApi.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] })
    },
  })

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const filteredApps =
    jobFilter === ''
      ? applications
      : applications.filter((a) => (typeof a.job_offer === 'object' ? a.job_offer?.id : a.job_offer) === jobFilter)

  const appsByStatus = STATUSES.reduce((acc, status) => {
    acc[status] = filteredApps.filter((a) => a.status === status)
    return acc
  }, {} as Record<ApplicationStatus, Application[]>)

  const handleDragStart = (event: DragStartEvent) => {
    const id = event.active.id
    setActiveId(typeof id === 'number' ? id : Number(id))
  }

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    setActiveId(null)
    if (!over) return
    const newStatus = String(over.id) as ApplicationStatus
    if (!STATUSES.includes(newStatus)) return
    const appId = typeof active.id === 'number' ? active.id : Number(active.id)
    const app = applications.find((a) => a.id === appId)
    if (!app || app.status === newStatus) return
    updateStatusMutation.mutate({ id: appId, status: newStatus })
  }

  const handleExportExcel = async () => {
    try {
      const { data } = await applicationsApi.exportExcel()
      downloadBlob(data as Blob, 'candidatures.xlsx')
    } catch {
      // ignore
    }
  }

  const handleExportShortlisted = async () => {
    try {
      const { data } = await applicationsApi.exportShortlistedExcel()
      downloadBlob(data as Blob, 'preselectionnes.xlsx')
    } catch {
      // ignore
    }
  }

  const activeApp = activeId ? applications.find((a) => a.id === activeId) : null

  return (
    <div className="min-w-0">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-slate-800">{t('pipeline.title')}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={jobFilter}
            onChange={(e) => setJobFilter(e.target.value === '' ? '' : Number(e.target.value))}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
          >
            <option value="">{t('pipeline.filterByJob')}</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>{j.title}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleExportShortlisted}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-4 w-4" />
            {t('pipeline.exportShortlisted')}
          </button>
          <button
            type="button"
            onClick={handleExportExcel}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-4 w-4" />
            {t('pipeline.exportExcel')}
          </button>
        </div>
      </div>

      <p className="mt-2 text-sm text-slate-500">{t('pipeline.dragToChange')}</p>

      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="mt-6 flex w-full min-w-0 gap-3 overflow-x-auto pb-4">
          {STATUSES.map((status) => (
            <PipelineColumn
              key={status}
              id={status}
              title={t(statusLabelKeys[status])}
              applications={appsByStatus[status]}
            />
          ))}
        </div>

        <DragOverlay>
          {activeApp ? (
            <div className="w-72 rounded-lg border border-slate-200 bg-white p-3 shadow-lg">
              <ApplicationCard application={activeApp} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  )
}
