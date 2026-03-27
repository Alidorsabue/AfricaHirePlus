/**
 * Menu utilisateur (avatar + nom) : dropdown avec profil, préférences, déconnexion.
 * Fermeture au clic extérieur.
 */
import { useRef, useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { User, Settings, LogOut, ChevronUp } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { resolveMediaUrl } from '../api/env'

/** Clés i18n pour afficher le rôle (admin, recruteur, candidat) */
const roleKeys: Record<string, string> = {
  admin: 'user.roleAdmin',
  super_admin: 'user.roleAdmin',
  recruiter: 'user.roleRecruiter',
  candidate: 'user.roleCandidate',
}

interface UserMenuProps {
  onOpenPreferences?: () => void
}

export default function UserMenu({ onOpenPreferences }: UserMenuProps) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Fermer le menu au clic en dehors
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open])

  const handleLogout = () => {
    setOpen(false)
    logout()
    navigate('/login')
  }

  const displayName = user
    ? `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username
    : ''
  const roleKey = user ? roleKeys[user.role] ?? 'user.roleRecruiter' : ''

  const avatarUrl = useMemo(() => resolveMediaUrl(user?.avatar), [user?.avatar])
  const [avatarBroken, setAvatarBroken] = useState(false)
  useEffect(() => {
    setAvatarBroken(false)
  }, [avatarUrl])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-slate-800 dark:hover:bg-slate-700"
        aria-expanded={open}
        aria-haspopup="true"
      >
        <div className="flex flex-col items-end">
          <span className="text-sm font-medium text-white">{displayName || user?.username}</span>
          <span className="text-xs text-slate-400">{t(roleKey)}</span>
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-violet-600 text-white">
          {avatarUrl && !avatarBroken ? (
            <img
              src={avatarUrl}
              alt=""
              className="h-full w-full object-cover"
              onError={() => setAvatarBroken(true)}
            />
          ) : (
            <User className="h-5 w-5" />
          )}
        </div>
        <ChevronUp
          className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${open ? '' : 'rotate-180'}`}
        />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 min-w-[240px] rounded-lg border border-slate-700 bg-slate-900 py-2 shadow-xl">
          <div className="border-b border-slate-700 px-4 py-3">
            <p className="font-medium text-white">{displayName || user?.username}</p>
            <p className="mt-0.5 truncate text-sm text-slate-400">{user?.email}</p>
          </div>
          <div className="py-1">
            <button
              type="button"
              onClick={() => {
                setOpen(false)
                navigate('/profil')
              }}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm text-white hover:bg-slate-800"
            >
              <User className="h-4 w-4 shrink-0" />
              {t('nav.profile')}
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false)
                onOpenPreferences?.()
              }}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm text-white hover:bg-slate-800"
            >
              <Settings className="h-4 w-4 shrink-0" />
              {t('nav.preferences')}
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm text-red-400 hover:bg-slate-800 hover:text-red-300"
            >
              <LogOut className="h-4 w-4 shrink-0" />
              {t('nav.logout')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
