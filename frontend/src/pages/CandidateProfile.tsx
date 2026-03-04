import { useState, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Mail, Phone, MapPin, Briefcase, GraduationCap, FileText, ExternalLink, Pencil, X, Languages, FileCheck } from 'lucide-react'
import { candidatesApi } from '../api/candidates'
import { applicationsApi } from '../api/applications'
import { unwrapList } from '../api/utils'
import type { Candidate, CandidateProfile, Application } from '../types'

export default function CandidateProfile() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const candidateId = Number(id)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    location: '',
    country: '',
    summary: '',
    experience_years: '' as number | string,
    education_level: '',
    current_position: '',
    linkedin_url: '',
    portfolio_url: '',
    skills: '' as string | string[],
  })

  const { data: candidate, isLoading } = useQuery({
    queryKey: ['candidate', candidateId],
    queryFn: () => candidatesApi.get(candidateId),
    enabled: !!candidateId,
  })

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Candidate>) => candidatesApi.update(candidateId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidate', candidateId] })
      setEditing(false)
    },
  })

  useEffect(() => {
    if (candidate?.data) {
      const c = candidate.data as Candidate
      setForm({
        first_name: c.first_name ?? '',
        last_name: c.last_name ?? '',
        email: c.email ?? '',
        phone: c.phone ?? '',
        location: c.location ?? '',
        country: c.country ?? '',
        summary: c.summary ?? '',
        experience_years: c.experience_years ?? '',
        education_level: c.education_level ?? '',
        current_position: c.current_position ?? '',
        linkedin_url: c.linkedin_url ?? '',
        portfolio_url: c.portfolio_url ?? '',
        skills: Array.isArray(c.skills) ? c.skills.join(', ') : (c.skills ?? ''),
      })
    }
  }, [candidate?.data])

  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: async () => unwrapList((await applicationsApi.list()).data),
    enabled: !!candidateId,
  })

  const candidateApplications = applications.filter(
    (a) => (typeof a.candidate === 'object' ? a.candidate?.id : a.candidate) === candidateId
  )

  const [coverLetterModalOpen, setCoverLetterModalOpen] = useState(false)
  const [selectedCoverLetter, setSelectedCoverLetter] = useState<string | null>(null)

  const statusMutation = useMutation({
    mutationFn: ({ appId, status }: { appId: number; status: string }) =>
      applicationsApi.updateStatus(appId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      queryClient.invalidateQueries({ queryKey: ['candidate', candidateId] })
    },
  })

  if (isLoading || !candidate?.data) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
      </div>
    )
  }

  const c = candidate.data as CandidateProfile

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    setForm((p) => ({ ...p, [name]: value }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateMutation.mutate({
      ...form,
      experience_years: form.experience_years === '' ? null : Number(form.experience_years),
      skills: typeof form.skills === 'string' ? form.skills.split(',').map((s) => s.trim()).filter(Boolean) : form.skills,
    })
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link to="/candidates" className="text-sm font-medium text-teal-600 hover:underline">
          ← {t('common.back')}
        </Link>
        {!editing ? (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            <Pencil className="h-4 w-4" />
            {t('common.edit')}
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 dark:border-slate-600 dark:text-slate-200"
            >
              {t('common.cancel')}
            </button>
          </div>
        )}
      </div>

      {editing ? (
        <form onSubmit={handleSubmit} className="mt-6 space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
          {updateMutation.error && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
              {(updateMutation.error as Error).message}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Prénom</label>
              <input name="first_name" value={form.first_name} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Nom</label>
              <input name="last_name" value={form.last_name} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Email</label>
              <input type="email" name="email" value={form.email} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Téléphone</label>
              <input name="phone" value={form.phone} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Ville / Lieu</label>
              <input name="location" value={form.location} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Pays</label>
              <input name="country" value={form.country} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('candidate.summary')}</label>
              <textarea name="summary" value={form.summary} onChange={handleChange} rows={4} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Années d'expérience</label>
              <input type="number" name="experience_years" value={form.experience_years} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('candidate.education')}</label>
              <input name="education_level" value={form.education_level} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('candidate.experience')}</label>
              <input name="current_position" value={form.current_position} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">LinkedIn</label>
              <input type="url" name="linkedin_url" value={form.linkedin_url} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Portfolio</label>
              <input type="url" name="portfolio_url" value={form.portfolio_url} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('candidate.skills')} (séparés par des virgules)</label>
              <input name="skills" value={typeof form.skills === 'string' ? form.skills : (form.skills as string[]).join(', ')} onChange={handleChange} className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100" />
            </div>
          </div>
          <div className="flex gap-3 pt-4">
            <button type="submit" disabled={updateMutation.isPending} className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50">
              {updateMutation.isPending ? t('common.loading') : t('common.save')}
            </button>
            <button type="button" onClick={() => setEditing(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 dark:border-slate-600 dark:text-slate-200">
              {t('common.cancel')}
            </button>
          </div>
        </form>
      ) : (
      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
              {c.first_name} {c.last_name}
            </h1>
            <p className="mt-1 text-slate-600 dark:text-slate-400">{t('candidate.fullName')}</p>
            <div className="mt-4 flex flex-wrap gap-4 text-sm text-slate-600 dark:text-slate-400">
              <a href={`mailto:${c.email}`} className="flex items-center gap-2 text-teal-600 hover:underline dark:text-teal-400">
                <Mail className="h-4 w-4" />
                {c.email}
              </a>
              {(c.phone || (c as CandidateProfile).cell_number) && (
                <span className="flex items-center gap-2">
                  <Phone className="h-4 w-4" />
                  {(c as CandidateProfile).cell_number || c.phone}
                </span>
              )}
              {(c.location || c.country) && (
                <span className="flex items-center gap-2">
                  <MapPin className="h-4 w-4" />
                  {[c.location, (c as CandidateProfile).city, c.country].filter(Boolean).join(', ')}
                </span>
              )}
              {(c as CandidateProfile).address && (
                <span className="block text-xs">{(c as CandidateProfile).address}</span>
              )}
              {(c as CandidateProfile).nationality && (
                <span className="text-xs">{(c as CandidateProfile).nationality}</span>
              )}
            </div>
            {(c.linkedin_url || c.portfolio_url) && (
              <div className="mt-4 flex gap-3">
                {c.linkedin_url && (
                  <a
                    href={c.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-teal-600 hover:underline"
                  >
                    LinkedIn <ExternalLink className="h-3 w-3" />
                  </a>
                )}
                {c.portfolio_url && (
                  <a
                    href={c.portfolio_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-teal-600 hover:underline"
                  >
                    Portfolio <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            )}
            {/* CV (pdf) et lettre de motivation */}
            {((c as CandidateProfile).resume_url || candidateApplications.some((a) => a.cover_letter?.trim() || a.cover_letter_document_url)) && (
              <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4 dark:border-slate-600">
                {(c as CandidateProfile).resume_url && (
                  <a
                    href={(c as CandidateProfile).resume_url!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700"
                  >
                    <FileText className="h-4 w-4" />
                    {t('candidate.openCvPdf')}
                  </a>
                )}
                {candidateApplications.some((a) => a.cover_letter?.trim()) && (
                  <button
                    type="button"
                    onClick={() => {
                      const firstWithLetter = candidateApplications.find((a) => a.cover_letter?.trim())
                      if (firstWithLetter?.cover_letter) {
                        setSelectedCoverLetter(firstWithLetter.cover_letter)
                        setCoverLetterModalOpen(true)
                      }
                    }}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
                  >
                    <FileCheck className="h-4 w-4" />
                    {t('candidate.openCoverLetter')}
                  </button>
                )}
              </div>
            )}
          </div>

          {c.summary && (
            <div>
              <h2 className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-200">
                <FileText className="h-5 w-5" />
                {t('candidate.summary')}
              </h2>
              <p className="mt-3 whitespace-pre-wrap text-slate-600 dark:text-slate-400">{c.summary}</p>
            </div>
          )}

          <div className="border-t border-slate-200 pt-6 dark:border-slate-600">
            <h2 className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-200">
              <Briefcase className="h-5 w-5" />
              {t('candidate.applications')}
            </h2>
            {candidateApplications.length === 0 ? (
              <p className="mt-3 text-slate-500 dark:text-slate-400">{t('candidate.noApplications')}</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {candidateApplications.map((app: Application) => {
                  const job = typeof app.job_offer === 'object' ? app.job_offer : null
                  const title = job?.title ?? `#${app.job_offer}`
                  const isShortlisted = app.status === 'shortlisted'
                  const hasCoverLetter = !!(app.cover_letter?.trim() || app.cover_letter_document_url)
                  return (
                    <li key={app.id} className="rounded-lg border border-slate-200 p-3 dark:border-slate-600">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link to={`/jobs/${typeof app.job_offer === 'object' ? app.job_offer?.id : app.job_offer}`} className="font-medium text-teal-600 hover:underline dark:text-teal-400">
                            {title}
                          </Link>
                          <Link to={`/applications/${app.id}`} className="text-xs text-slate-500 hover:underline dark:text-slate-400">
                            {t('candidate.viewApplication')}
                          </Link>
                        </div>
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-600 dark:text-slate-200">
                          {app.status}
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {hasCoverLetter && (
                          <>
                            {app.cover_letter_document_url ? (
                              <a
                                href={app.cover_letter_document_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-sm text-teal-600 hover:underline dark:text-teal-400"
                              >
                                {t('candidate.openCoverLetterPdf')}
                              </a>
                            ) : null}
                            {app.cover_letter?.trim() && (
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedCoverLetter(app.cover_letter)
                                  setCoverLetterModalOpen(true)
                                }}
                                className="inline-flex items-center gap-1 text-sm text-teal-600 hover:underline dark:text-teal-400"
                              >
                                {t('candidate.openCoverLetter')}
                              </button>
                            )}
                          </>
                        )}
                        {isShortlisted ? (
                          <button
                            type="button"
                            onClick={() => statusMutation.mutate({ appId: app.id, status: 'rejected_selection' })}
                            disabled={statusMutation.isPending}
                            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
                          >
                            {t('candidate.removeFromShortlist')}
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => statusMutation.mutate({ appId: app.id, status: 'shortlisted' })}
                            disabled={statusMutation.isPending}
                            className="rounded bg-teal-600 px-2 py-1 text-xs font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                          >
                            {t('candidate.shortlist')}
                          </button>
                        )}
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="border-t border-slate-200 pt-6 dark:border-slate-600 lg:border-t-0 lg:pt-0">
            <h2 className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-200">
              <Briefcase className="h-5 w-5" />
              {t('candidate.experience')}
            </h2>
            {c.current_position && (
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{c.current_position}</p>
            )}
            {c.experience_years != null && (
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {c.experience_years} an(s) d&apos;expérience
              </p>
            )}
            {Array.isArray(c.experience) && c.experience.length > 0 ? (
              <ul className="mt-3 space-y-3">
                {c.experience.map((exp: Record<string, unknown>, i: number) => (
                  <li key={i} className="rounded-lg border border-slate-100 p-2 text-sm dark:border-slate-600">
                    <p className="font-medium text-slate-800 dark:text-slate-200">
                      {String(exp.job_title || exp.company_name || '—')}
                    </p>
                    {Boolean(exp.company_name ?? exp.job_title) && String(exp.company_name) !== String(exp.job_title) && (
                      <p className="text-slate-600 dark:text-slate-400">{String(exp.company_name ?? '')}</p>
                    )}
                    {Boolean(exp.start_year ?? exp.end_year) && (
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {String([exp.start_month, exp.start_year].filter(Boolean).join(' '))} – {String([exp.end_month, exp.end_year].filter(Boolean).join(' ') || '...')}
                      </p>
                    )}
                    {Boolean(exp.responsibilities) && (
                      <p className="mt-1 whitespace-pre-wrap text-xs text-slate-600 dark:text-slate-400">
                        {String(exp.responsibilities).slice(0, 200)}
                        {String(exp.responsibilities).length > 200 ? '…' : ''}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-slate-500 dark:text-slate-400">{t('candidate.noExperience')}</p>
            )}
          </div>
          <div>
            <h2 className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-200">
              <GraduationCap className="h-5 w-5" />
              {t('candidate.education')}
            </h2>
            {c.education_level && (
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{c.education_level}</p>
            )}
            {Array.isArray(c.education) && c.education.length > 0 ? (
              <ul className="mt-3 space-y-2">
                {c.education.map((edu: Record<string, unknown>, i: number) => (
                  <li key={i} className="rounded-lg border border-slate-100 p-2 text-sm dark:border-slate-600">
                    <p className="font-medium text-slate-800 dark:text-slate-200">
                      {String([edu.degree_type, edu.discipline].filter(Boolean).join(' — ') || '—')}
                    </p>
                    {edu.institution != null && String(edu.institution) !== '' && (
                      <p className="text-slate-600 dark:text-slate-400">{String(edu.institution)}</p>
                    )}
                    {Boolean(edu.start_year ?? edu.end_year) && (
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {String(edu.start_year ?? '')} – {String(edu.end_year ?? '')}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-slate-500 dark:text-slate-400">{t('candidate.noEducation')}</p>
            )}
          </div>
          {Array.isArray(c.languages) && c.languages.length > 0 && (
            <div>
              <h2 className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-200">
                <Languages className="h-5 w-5" />
                {t('candidate.languages')}
              </h2>
              <ul className="mt-2 flex flex-wrap gap-2">
                {c.languages.map((lang: Record<string, unknown>, i: number) => (
                  <li key={i} className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700 dark:bg-slate-600 dark:text-slate-200">
                    {String(lang.language || lang.name || '—')}
                    {(lang.speaking_proficiency != null || lang.level != null) && ` (${String(lang.speaking_proficiency ?? lang.level ?? '')})`}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {c.skills && c.skills.length > 0 && (
            <div>
              <h2 className="font-semibold text-slate-800 dark:text-slate-200">{t('candidate.skills')}</h2>
              <div className="mt-2 flex flex-wrap gap-2">
                {c.skills.map((skill: string) => (
                  <span
                    key={skill}
                    className="rounded-full bg-teal-50 px-3 py-1 text-sm text-teal-700"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
        </div>
      </div>
      )}

      {/* Modal lettre de motivation */}
      {coverLetterModalOpen && selectedCoverLetter != null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => { setCoverLetterModalOpen(false); setSelectedCoverLetter(null) }}>
          <div className="max-h-[85vh] w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-xl dark:bg-slate-800" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-600">
              <h3 className="font-semibold text-slate-800 dark:text-slate-200">{t('candidate.coverLetter')}</h3>
              <button type="button" onClick={() => { setCoverLetterModalOpen(false); setSelectedCoverLetter(null) }} className="rounded p-1 hover:bg-slate-100 dark:hover:bg-slate-700">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-y-auto p-4">
              <p className="whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-300">{selectedCoverLetter}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
