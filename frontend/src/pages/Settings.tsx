import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Building2, User, SlidersHorizontal } from 'lucide-react'

const cards = [
  { to: '/company', icon: Building2, titleKey: 'settings.company', descKey: 'settings.companyDesc' },
  { to: '/profil', icon: User, titleKey: 'settings.account', descKey: 'settings.accountDesc' },
] as const

export default function Settings() {
  const { t } = useTranslation()

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        {t('nav.settings')}
      </h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{t('settings.subtitle')}</p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {cards.map(({ to, icon: Icon, titleKey, descKey }) => (
          <Link
            key={to}
            to={to}
            className="flex gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-teal-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-800/50 dark:hover:border-teal-600"
          >
            <div className="rounded-lg bg-slate-100 p-3 dark:bg-slate-700">
              <Icon className="h-6 w-6 text-teal-600 dark:text-teal-400" />
            </div>
            <div>
              <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t(titleKey)}</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{t(descKey)}</p>
            </div>
          </Link>
        ))}
        <div className="flex gap-4 rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-5 dark:border-slate-700 dark:bg-slate-900/30">
          <div className="rounded-lg bg-slate-100 p-3 dark:bg-slate-700">
            <SlidersHorizontal className="h-6 w-6 text-slate-500" />
          </div>
          <div>
            <h2 className="font-semibold text-slate-800 dark:text-slate-100">
              {t('settings.preferences')}
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {t('settings.preferencesDesc')}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
