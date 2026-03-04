import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard,
  Briefcase,
  GitBranch,
  Users,
  FileQuestion,
  Mail,
  Building2,
  Bell,
} from 'lucide-react'
import UserMenu from './UserMenu'
import PreferencesModal from './PreferencesModal'

const nav = [
  { to: '/', icon: LayoutDashboard, key: 'dashboard' },
  { to: '/jobs', icon: Briefcase, key: 'jobs' },
  { to: '/pipeline', icon: GitBranch, key: 'pipeline' },
  { to: '/candidates', icon: Users, key: 'candidates' },
  { to: '/tests', icon: FileQuestion, key: 'tests' },
  { to: '/emails', icon: Mail, key: 'emailTemplates' },
  { to: '/company', icon: Building2, key: 'company' },
] as const

export default function Layout({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation()
  const [preferencesOpen, setPreferencesOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
      <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex h-16 items-center gap-3 border-b border-slate-200 px-4 dark:border-slate-800">
          <Link to="/" className="flex items-center gap-2">
            <img
              src="/logo/AfricaHire+.png"
              alt="AfricaHire+"
              className="h-9 w-auto object-contain"
              onError={(e) => {
                const target = e.currentTarget
                target.style.display = 'none'
                if (target.nextElementSibling) return
                const span = document.createElement('span')
                span.className = 'font-bold text-teal-600 text-lg dark:text-teal-400'
                span.textContent = 'AfricaHire+'
                target.parentNode?.appendChild(span)
              }}
            />
          </Link>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {nav.map(({ to, icon: Icon, key }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200'
                }`
              }
            >
              <Icon className="h-5 w-5 shrink-0" />
              {t(`nav.${key}`)}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="ml-64 flex flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-end gap-2 border-b border-slate-200 bg-slate-900 px-6 dark:border-slate-800">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white dark:hover:bg-slate-700"
            aria-label="Notifications"
          >
            <Bell className="h-5 w-5" />
          </button>
          <UserMenu onOpenPreferences={() => setPreferencesOpen(true)} />
        </header>

        <main className="min-w-0 flex-1 p-6 lg:p-8">
          {children}
        </main>
      </div>

      <PreferencesModal open={preferencesOpen} onClose={() => setPreferencesOpen(false)} />
    </div>
  )
}
