import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Shield, FileText, Users, ScrollText } from 'lucide-react'

export default function RgpdAudit() {
  const { t } = useTranslation()

  const items = [
    {
      icon: ScrollText,
      titleKey: 'rgpdAudit.auditTitle',
      descKey: 'rgpdAudit.auditDesc',
      to: '/applications',
      linkKey: 'rgpdAudit.auditLink',
    },
    {
      icon: Users,
      titleKey: 'rgpdAudit.anonymizeTitle',
      descKey: 'rgpdAudit.anonymizeDesc',
      to: '/candidates',
      linkKey: 'rgpdAudit.anonymizeLink',
    },
    {
      icon: FileText,
      titleKey: 'rgpdAudit.exportTitle',
      descKey: 'rgpdAudit.exportDesc',
      to: null,
      linkKey: 'rgpdAudit.exportNote',
    },
  ] as const

  return (
    <div>
      <div className="flex items-center gap-3">
        <div className="rounded-xl bg-teal-100 p-3 dark:bg-teal-900/40">
          <Shield className="h-7 w-7 text-teal-700 dark:text-teal-300" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
            {t('nav.rgpdAudit')}
          </h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{t('rgpdAudit.subtitle')}</p>
        </div>
      </div>

      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        {items.map(({ icon: Icon, titleKey, descKey, to, linkKey }) => (
          <div
            key={titleKey}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800/50"
          >
            <Icon className="h-6 w-6 text-teal-600 dark:text-teal-400" />
            <h2 className="mt-3 font-semibold text-slate-800 dark:text-slate-100">{t(titleKey)}</h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{t(descKey)}</p>
            {to ? (
              <Link
                to={to}
                className="mt-4 inline-block text-sm font-medium text-teal-600 hover:underline dark:text-teal-400"
              >
                {t(linkKey)}
              </Link>
            ) : (
              <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">{t(linkKey)}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
