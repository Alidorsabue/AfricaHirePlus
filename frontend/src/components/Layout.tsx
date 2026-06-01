import { useState, useEffect, type ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Bell } from 'lucide-react'
import UserMenu from './UserMenu'
import PreferencesModal from './PreferencesModal'
import { useAuth } from '../contexts/AuthContext'
import { companiesApi } from '../api/companies'
import { resolveMediaUrl } from '../api/env'
import { recruiterNavSections, type NavBadgeKey } from '../config/recruiterNav'
import { useRecruiterNavBadges } from '../hooks/useRecruiterNavBadges'
import type { Company } from '../types'

function NavBadge({ count, active }: { count: number; active: boolean }) {
  if (count <= 0) return null
  return (
    <span
      className={`ml-auto flex h-5 min-w-[1.25rem] shrink-0 items-center justify-center rounded-full px-1.5 text-xs font-semibold tabular-nums ${
        active
          ? 'bg-teal-600 text-white'
          : 'bg-slate-700 text-slate-300'
      }`}
    >
      {count > 99 ? '99+' : count}
    </span>
  )
}

function isNavItemActive(
  pathname: string,
  to: string,
  end?: boolean,
  alsoActiveOn?: string[]
): boolean {
  if (alsoActiveOn?.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return true
  }
  if (end) return pathname === to
  if (to === '/') return pathname === '/'
  return pathname === to || pathname.startsWith(`${to}/`)
}

export default function Layout({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const [preferencesOpen, setPreferencesOpen] = useState(false)
  const { user } = useAuth()
  const badges = useRecruiterNavBadges()
  const companyId = user?.company != null ? Number(user.company) : null
  const [company, setCompany] = useState<Company | null>(null)

  useEffect(() => {
    let cancelled = false
    if (!companyId) {
      setCompany(null)
      return
    }
    companiesApi
      .get(companyId)
      .then(({ data }) => {
        if (!cancelled) setCompany(data)
      })
      .catch(() => {
        if (!cancelled) setCompany(null)
      })
    return () => {
      cancelled = true
    }
  }, [companyId])
  const companyLogoUrl = resolveMediaUrl(company?.logo)

  const getBadge = (key?: NavBadgeKey): number => {
    if (!key) return 0
    return badges[key] ?? 0
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 dark:bg-slate-950">
      <header className="fixed left-0 right-0 top-0 z-50 flex h-16 shrink-0 items-center justify-between gap-4 border-b border-slate-800 bg-slate-900 px-4 shadow-sm lg:px-6">
        <div className="flex min-w-0 flex-1 items-center gap-4 sm:gap-6">
          <Link to="/" className="flex shrink-0 items-center gap-2">
            <img
              src="/logo/AfricaHire+.png"
              alt="AfricaHire+"
              className="h-9 w-auto object-contain"
              onError={(e) => {
                const target = e.currentTarget
                target.style.display = 'none'
                if (target.nextElementSibling) return
                const span = document.createElement('span')
                span.className = 'font-bold text-lg text-teal-400'
                span.textContent = 'AfricaHire+'
                target.parentNode?.appendChild(span)
              }}
            />
            <span className="font-semibold text-white">AfricaHire+</span>
          </Link>
          {company && (
            <div className="flex min-w-0 items-center gap-2 border-l border-slate-700 pl-4 sm:pl-6">
              {companyLogoUrl ? (
                <img
                  src={companyLogoUrl}
                  alt=""
                  className="h-8 w-8 shrink-0 rounded-md bg-slate-800 object-contain"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
                />
              ) : (
                <div className="h-8 w-8 shrink-0 rounded-md bg-slate-700" aria-hidden />
              )}
              <span className="truncate text-sm font-medium text-slate-100">{company.name}</span>
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
            aria-label="Notifications"
          >
            <Bell className="h-5 w-5" />
          </button>
          <UserMenu onOpenPreferences={() => setPreferencesOpen(true)} />
        </div>
      </header>

      <div className="flex flex-1 pt-16">
        <aside className="fixed left-0 top-16 z-40 flex h-[calc(100vh-4rem)] w-64 flex-col border-r border-slate-800 bg-slate-950">
          <nav className="flex flex-1 flex-col overflow-y-auto px-2 py-3">
            {recruiterNavSections.map(({ sectionKey, items }) => (
              <div key={sectionKey} className="mb-1">
                <p className="px-3 pb-1.5 pt-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500 first:pt-1">
                  {t(`nav.${sectionKey}`)}
                </p>
                <ul className="flex flex-col gap-0.5">
                  {items.map(({ to, icon: Icon, labelKey, badgeKey, end, alsoActiveOn }) => {
                    const active = isNavItemActive(pathname, to, end, alsoActiveOn)
                    const badgeCount = getBadge(badgeKey)
                    return (
                      <li key={to + labelKey}>
                        <NavLink
                          to={to}
                          end={end}
                          className={() =>
                            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                              active
                                ? 'bg-emerald-200 text-slate-900'
                                : 'text-slate-400 hover:bg-slate-800/80 hover:text-slate-200'
                            }`
                          }
                        >
                          <Icon className="h-5 w-5 shrink-0" strokeWidth={active ? 2.25 : 2} />
                          <span className="min-w-0 flex-1 truncate">{t(`nav.${labelKey}`)}</span>
                          <NavBadge count={badgeCount} active={active} />
                        </NavLink>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </aside>

        <div className="ml-64 flex min-h-[calc(100vh-4rem)] min-w-0 flex-1 flex-col">
          <main className="min-w-0 flex-1 p-6 lg:p-8">{children}</main>
        </div>
      </div>

      <PreferencesModal open={preferencesOpen} onClose={() => setPreferencesOpen(false)} />
    </div>
  )
}
