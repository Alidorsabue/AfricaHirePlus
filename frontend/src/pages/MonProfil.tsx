/**
 * Page « Mon profil » pour le candidat connecté : avatar + détails en sections ouvrables.
 * Les données viennent de GET /api/candidates/me/ (profil sauvegardé lors des candidatures).
 */
import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  User,
  ChevronDown,
  ChevronRight,
  Mail,
  Phone,
  MapPin,
  Briefcase,
  GraduationCap,
  Languages,
  Users,
  FileText,
  ExternalLink,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { resolveMediaUrl } from '../api/env'
import { candidatesApi } from '../api/candidates'
import type { CandidateProfile } from '../types'

function Section({
  title,
  open,
  onToggle,
  children,
}: {
  title: string
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800 overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 text-left font-medium text-slate-800 dark:text-slate-100 hover:bg-slate-50 dark:hover:bg-slate-700/50"
      >
        <span>{title}</span>
        {open ? (
          <ChevronDown className="h-5 w-5 text-slate-500" />
        ) : (
          <ChevronRight className="h-5 w-5 text-slate-500" />
        )}
      </button>
      {open && <div className="border-t border-slate-200 px-4 py-4 dark:border-slate-700">{children}</div>}
    </div>
  )
}

export default function MonProfil() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [openPersonal, setOpenPersonal] = useState(true)
  const [openEducation, setOpenEducation] = useState(false)
  const [openExperience, setOpenExperience] = useState(false)
  const [openLanguages, setOpenLanguages] = useState(false)
  const [openReferences, setOpenReferences] = useState(false)

  const { data: profileRes, isLoading, error } = useQuery({
    queryKey: ['candidateProfile'],
    queryFn: () => candidatesApi.me(),
    retry: (_, err) => (err as { response?: { status?: number } })?.response?.status !== 404,
  })
  const profile = profileRes?.data as CandidateProfile | undefined
  const hasProfile = profile && typeof profile === 'object'
  const avatarUrl = useMemo(() => resolveMediaUrl(user?.avatar), [user?.avatar])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-teal-500 border-t-transparent dark:border-teal-400" />
      </div>
    )
  }

  if (error || !hasProfile) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
          {t('candidat.monProfil')}
        </h1>
        <p className="mt-1 text-slate-600 dark:text-slate-400">{t('candidat.monProfilHint')}</p>
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-8 text-center dark:border-slate-700 dark:bg-slate-800">
          <User className="mx-auto h-14 w-14 text-slate-400 dark:text-slate-500" />
          <p className="mt-4 text-slate-600 dark:text-slate-300">{t('candidat.noProfileYet')}</p>
          <Link
            to="/candidat/offres"
            className="mt-4 inline-block rounded-lg bg-teal-600 px-4 py-2 font-medium text-white hover:bg-teal-700"
          >
            {t('candidat.browseJobs')}
          </Link>
        </div>
      </div>
    )
  }

  const fullName = [profile.first_name, profile.last_name].filter(Boolean).join(' ') || user?.email

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        {t('candidat.monProfil')}
      </h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{t('candidat.monProfilHint')}</p>

      <div className="mt-8 flex flex-col items-center gap-6 sm:flex-row sm:items-start">
        <Link
          to="/candidat/offres"
          className="shrink-0 rounded-full ring-2 ring-teal-500/30 transition hover:ring-teal-500/60 focus:outline-none focus:ring-2 focus:ring-teal-500"
          title={t('candidat.openProfile')}
          aria-label={t('candidat.openProfile')}
        >
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt=""
              className="h-24 w-24 rounded-full object-cover sm:h-28 sm:w-28"
            />
          ) : (
            <div className="flex h-24 w-24 items-center justify-center rounded-full bg-teal-100 text-teal-700 dark:bg-teal-900/50 dark:text-teal-300 sm:h-28 sm:w-28">
              <User className="h-12 w-12 sm:h-14 sm:w-14" />
            </div>
          )}
        </Link>
        <div className="min-w-0 flex-1 text-center sm:text-left">
          <p className="text-xl font-semibold text-slate-800 dark:text-slate-100">{fullName}</p>
          {profile.email && (
            <a
              href={`mailto:${profile.email}`}
              className="mt-1 flex items-center justify-center gap-2 text-teal-600 hover:underline dark:text-teal-400 sm:justify-start"
            >
              <Mail className="h-4 w-4 shrink-0" />
              {profile.email}
            </a>
          )}
          {(profile.current_position || profile.location) && (
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              {[profile.current_position, profile.location].filter(Boolean).join(' · ')}
            </p>
          )}
        </div>
      </div>

      <div className="mt-8 space-y-4">
        <Section
          title={t('publicJob.personalDetails')}
          open={openPersonal}
          onToggle={() => setOpenPersonal((v) => !v)}
        >
          <div className="grid gap-3 text-sm sm:grid-cols-2">
            {(profile.title || profile.preferred_name) && (
              <p>
                <span className="text-slate-500 dark:text-slate-400">{profile.title}</span>
                {profile.preferred_name && ` · ${profile.preferred_name}`}
              </p>
            )}
            {profile.date_of_birth && <p>{profile.date_of_birth}</p>}
            {profile.gender && <p>{profile.gender}</p>}
            {profile.phone && (
              <p className="flex items-center gap-2">
                <Phone className="h-4 w-4 shrink-0" />
                {profile.phone}
              </p>
            )}
            {profile.cell_number && (
              <p className="flex items-center gap-2">
                <Phone className="h-4 w-4 shrink-0" />
                {profile.cell_number}
              </p>
            )}
            {(profile.address || profile.city) && (
              <p className="flex items-start gap-2 sm:col-span-2">
                <MapPin className="h-4 w-4 shrink-0 mt-0.5" />
                <span>
                  {[profile.address, profile.address_line2, profile.city, profile.postcode, profile.country]
                    .filter(Boolean)
                    .join(', ')}
                </span>
              </p>
            )}
            {profile.nationality && <p>{profile.nationality}</p>}
            {profile.second_nationality && <p>{profile.second_nationality}</p>}
          </div>
        </Section>

        {Array.isArray(profile.education) && profile.education.some((e) => e.institution || e.discipline) && (
          <Section
            title={t('candidate.education')}
            open={openEducation}
            onToggle={() => setOpenEducation((v) => !v)}
          >
            <ul className="space-y-4">
              {profile.education.map((e, i) => (
                <li key={i} className="flex gap-3 border-b border-slate-100 pb-4 last:border-0 last:pb-0 dark:border-slate-700">
                  <GraduationCap className="h-5 w-5 shrink-0 text-teal-600 dark:text-teal-400" />
                  <div>
                    {(e.institution as string) && <p className="font-medium">{e.institution as string}</p>}
                    {(e.degree_type as string) && <p className="text-slate-600 dark:text-slate-400">{e.degree_type as string}</p>}
                    {(e.discipline as string) && <p className="text-slate-600 dark:text-slate-400">{e.discipline as string}</p>}
                    {(e.start_year as string) || (e.end_year as string) ? (
                      <p className="text-xs text-slate-500">{[e.start_year, e.end_year].filter(Boolean).join(' – ')}</p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {Array.isArray(profile.experience) && profile.experience.some((e) => e.job_title || e.company_name) && (
          <Section
            title={t('candidate.experience')}
            open={openExperience}
            onToggle={() => setOpenExperience((v) => !v)}
          >
            <ul className="space-y-4">
              {profile.experience.map((e, i) => (
                <li key={i} className="flex gap-3 border-b border-slate-100 pb-4 last:border-0 last:pb-0 dark:border-slate-700">
                  <Briefcase className="h-5 w-5 shrink-0 text-teal-600 dark:text-teal-400" />
                  <div>
                    {(e.job_title as string) && <p className="font-medium">{e.job_title as string}</p>}
                    {(e.company_name as string) && <p className="text-slate-600 dark:text-slate-400">{e.company_name as string}</p>}
                    {(e.responsibilities as string) && (
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400 line-clamp-3">{e.responsibilities as string}</p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {Array.isArray(profile.languages) && profile.languages.some((l) => l.language) && (
          <Section
            title={t('publicJob.languages')}
            open={openLanguages}
            onToggle={() => setOpenLanguages((v) => !v)}
          >
            <ul className="flex flex-wrap gap-3">
              {profile.languages.map((l, i) => (
                <li key={i} className="flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-2 dark:bg-slate-700">
                  <Languages className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                  <span>{(l.language as string) || ''}</span>
                  {(l.speaking_proficiency as string) && (
                    <span className="text-xs text-slate-500">({l.speaking_proficiency as string})</span>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {Array.isArray(profile.references) && profile.references.some((r) => r.first_name || r.email) && (
          <Section
            title={t('publicJob.references')}
            open={openReferences}
            onToggle={() => setOpenReferences((v) => !v)}
          >
            <ul className="space-y-3">
              {profile.references.map((r, i) => (
                <li key={i} className="flex gap-3">
                  <Users className="h-5 w-5 shrink-0 text-teal-600 dark:text-teal-400" />
                  <div>
                    <p className="font-medium">{(r.first_name as string) || ''} {(r.last_name as string) || ''}</p>
                    {(r.job_title as string) && <p className="text-sm text-slate-600 dark:text-slate-400">{r.job_title as string}</p>}
                    {(r.organization as string) && <p className="text-sm text-slate-600 dark:text-slate-400">{r.organization as string}</p>}
                    {(r.email as string) && (
                      <a href={`mailto:${r.email}`} className="text-sm text-teal-600 hover:underline dark:text-teal-400">{r.email as string}</a>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {(profile.summary || profile.linkedin_url || profile.portfolio_url || profile.resume_url) && (
          <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
            <h3 className="mb-3 font-medium text-slate-800 dark:text-slate-100">{t('candidate.summary')}</h3>
            {profile.summary && (
              <p className="mb-3 flex gap-2 text-sm text-slate-600 dark:text-slate-400">
                <FileText className="h-4 w-4 shrink-0 mt-0.5" />
                <span className="whitespace-pre-wrap">{profile.summary}</span>
              </p>
            )}
            <div className="flex flex-wrap gap-3">
              {profile.linkedin_url && (
                <a
                  href={profile.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm text-teal-600 hover:underline dark:text-teal-400"
                >
                  <ExternalLink className="h-4 w-4" />
                  LinkedIn
                </a>
              )}
              {profile.portfolio_url && (
                <a
                  href={profile.portfolio_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm text-teal-600 hover:underline dark:text-teal-400"
                >
                  <ExternalLink className="h-4 w-4" />
                  Portfolio
                </a>
              )}
              {profile.resume_url && (
                <a
                  href={profile.resume_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm text-teal-600 hover:underline dark:text-teal-400"
                >
                  <FileText className="h-4 w-4" />
                  CV
                </a>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
