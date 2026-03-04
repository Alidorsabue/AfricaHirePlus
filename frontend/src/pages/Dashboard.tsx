import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Briefcase, Users, FileText, UserCheck } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { applicationsApi } from '../api/applications'
import { jobsApi } from '../api/jobs'
import { candidatesApi } from '../api/candidates'
import { unwrapList } from '../api/utils'

export default function Dashboard() {
  const { t } = useTranslation()
  const { user } = useAuth()

  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: async () => unwrapList((await applicationsApi.list()).data),
  })

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => unwrapList((await jobsApi.list()).data),
  })

  const { data: candidates = [] } = useQuery({
    queryKey: ['candidates'],
    queryFn: async () => unwrapList((await candidatesApi.list()).data),
  })

  const shortlisted = applications.filter((a) => a.status === 'shortlisted').length
  const activeJobs = jobs.filter((j) => j.status === 'published').length

  const stats = [
    { label: t('dashboard.stats.applications'), value: applications.length, icon: FileText, color: 'bg-blue-500' },
    { label: t('dashboard.stats.jobs'), value: activeJobs, icon: Briefcase, color: 'bg-teal-500' },
    { label: t('dashboard.stats.candidates'), value: candidates.length, icon: Users, color: 'bg-amber-500' },
    { label: t('dashboard.stats.shortlisted'), value: shortlisted, icon: UserCheck, color: 'bg-emerald-500' },
  ]

  const recent = applications.slice(0, 8)

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800">
        {t('dashboard.title')}, {user?.first_name || user?.username}
      </h1>
      <p className="mt-1 text-slate-600">{t('dashboard.welcome')}</p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div
            key={label}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-600">{label}</span>
              <div className={`rounded-lg p-2 ${color}`}>
                <Icon className="h-5 w-5 text-white" />
              </div>
            </div>
            <p className="mt-2 text-2xl font-bold text-slate-800">{value}</p>
          </div>
        ))}
      </div>

      <div className="mt-8 rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h2 className="font-semibold text-slate-800">{t('dashboard.recentApplications')}</h2>
          <Link
            to="/pipeline"
            className="text-sm font-medium text-teal-600 hover:underline"
          >
            {t('dashboard.viewAll')}
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-slate-600">
                <th className="px-6 py-3 font-medium">Candidat</th>
                <th className="px-6 py-3 font-medium">Offre</th>
                <th className="px-6 py-3 font-medium">Statut</th>
                <th className="px-6 py-3 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {recent.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-8 text-center text-slate-500">
                    Aucune candidature récente.
                  </td>
                </tr>
              ) : (
                recent.map((app) => {
                  const candidate = typeof app.candidate === 'object' ? app.candidate : null
                  const job = typeof app.job_offer === 'object' ? app.job_offer : null
                  const name = candidate
                    ? `${candidate.first_name} ${candidate.last_name}`.trim() || candidate.email
                    : `#${app.candidate}`
                  const title = job?.title ?? `#${app.job_offer}`
                  return (
                    <tr
                      key={app.id}
                      className="border-b border-slate-100 hover:bg-slate-50"
                    >
                      <td className="px-6 py-3">
                        <Link
                          to={candidate ? `/candidates/${candidate.id}` : '#'}
                          className="font-medium text-teal-600 hover:underline"
                        >
                          {name}
                        </Link>
                      </td>
                      <td className="px-6 py-3 text-slate-700">{title}</td>
                      <td className="px-6 py-3">
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                          {app.status}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-slate-500">
                        {new Date(app.applied_at).toLocaleDateString()}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
