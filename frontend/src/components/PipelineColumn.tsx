import { useDraggable, useDroppable } from '@dnd-kit/core'
import type { Application, ApplicationStatus } from '../types'
import { ApplicationCard } from './ApplicationCard'

interface PipelineColumnProps {
  id: ApplicationStatus
  title: string
  applications: Application[]
}

export function PipelineColumn({ id, title, applications }: PipelineColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id })

  return (
    <div
      ref={setNodeRef}
      className={`flex h-full w-0 min-w-[130px] flex-1 flex-shrink-0 flex-col rounded-xl border-2 bg-slate-50/80 p-3 transition-colors dark:bg-slate-800/80 dark:border-slate-600 ${
        isOver ? 'border-teal-400 bg-teal-50/50 dark:bg-teal-900/40 dark:border-teal-500' : 'border-slate-200 dark:border-slate-600'
      }`}
    >
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200">{title}</h3>
        <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-600 dark:text-slate-300">
          {applications.length}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2 overflow-y-auto">
        {applications.map((app) => (
          <DraggableCard key={app.id} application={app} />
        ))}
      </div>
    </div>
  )
}

function DraggableCard({ application }: { application: Application }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: application.id,
  })

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined

  if (isDragging) {
    return <div ref={setNodeRef} style={style} className="opacity-50" />
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="cursor-grab rounded-lg border border-slate-200 bg-white p-3 shadow-sm active:cursor-grabbing"
    >
      <ApplicationCard application={application} />
    </div>
  )
}
