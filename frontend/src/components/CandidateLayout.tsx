import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { User } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { resolveMediaUrl } from '../api/env'

export default function CandidateLayout({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const avatarUrl = useMemo(() => resolveMediaUrl(user?.avatar), [user?.avatar])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 dark:bg-slate-950">
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-900 sm:px-6">
        <Link to="/candidat" className="flex items-center gap-2">
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
          <span className="hidden font-medium text-slate-700 dark:text-slate-200 sm:inline">
            {t('candidat.space')}
          </span>
        </Link>
        <div className="flex items-center gap-2 sm:gap-3">
          <span className="hidden text-sm text-slate-600 dark:text-slate-400 sm:inline">
            {user?.first_name} {user?.last_name}
          </span>
          <Link
            to="/candidat/offres"
            className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            {t('candidat.browseJobs')}
          </Link>
          <Link
            to="/candidat/profil"
            className="flex shrink-0 items-center justify-center rounded-full ring-2 ring-transparent transition hover:ring-teal-500/50 focus:outline-none focus:ring-2 focus:ring-teal-500"
            title={t('candidat.openProfile')}
            aria-label={t('candidat.openProfile')}
          >
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt=""
                className="h-9 w-9 rounded-full object-cover"
              />
            ) : (
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-teal-100 text-teal-700 dark:bg-teal-900/50 dark:text-teal-300">
                <User className="h-5 w-5" />
              </div>
            )}
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            {t('nav.logout')}
          </button>
        </div>
      </header>
      <main className="min-w-0 flex-1 p-4 sm:p-6">{children}</main>
    </div>
  )
}
