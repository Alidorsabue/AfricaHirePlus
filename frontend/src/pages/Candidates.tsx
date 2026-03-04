import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { candidatesApi } from '../api/candidates'
import { unwrapList } from '../api/utils'
import type { Candidate } from '../types'

function downloadBlob(blob: Blob, filename: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function Candidates() {
  const { t } = useTranslation()

  const { data: candidates = [], isLoading } = useQuery({
    queryKey: ['candidates'],
    queryFn: async () => unwrapList((await candidatesApi.list()).data),
  })

  const handleExportExcel = async () => {
    try {
      const { data } = await candidatesApi.exportExcel()
      downloadBlob(data as Blob, 'candidats.xlsx')
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
        <h1 className="text-2xl font-bold text-slate-800">{t('candidate.profile')}</h1>
        <button
          type="button"
          onClick={handleExportExcel}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          <Download className="h-4 w-4" />
          {t('candidate.exportExcel')}
        </button>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm">
        {candidates.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-500">{t('candidate.noApplications')}</div>
        ) : (
          <ul className="divide-y divide-slate-200">
            {(candidates as Candidate[]).map((c) => (
              <li key={c.id} className="px-6 py-4 hover:bg-slate-50">
                <Link
                  to={`/candidates/${c.id}`}
                  className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <span className="font-medium text-teal-600 hover:underline">
                      {c.first_name} {c.last_name}
                    </span>
                    <span className="ml-2 text-slate-500">{c.email}</span>
                  </div>
                  <div className="text-sm text-slate-500">
                    {c.current_position || '—'} · {c.country || '—'}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
