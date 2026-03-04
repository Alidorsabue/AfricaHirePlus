import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Globe, Sun, Moon, Monitor, Save, Info } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import type { ThemeMode } from '../contexts/ThemeContext'

interface PreferencesModalProps {
  open: boolean
  onClose: () => void
}

export default function PreferencesModal({ open, onClose }: PreferencesModalProps) {
  const { t } = useTranslation()
  const { theme, setTheme } = useTheme()
  const { i18n } = useTranslation()
  const [lang, setLang] = useState(i18n.language === 'fr' ? 'fr' : 'en')
  const [themeLocal, setThemeLocal] = useState<ThemeMode>(theme)

  useEffect(() => {
    if (open) {
      setLang(i18n.language === 'fr' ? 'fr' : 'en')
      setThemeLocal(theme)
    }
  }, [open, i18n.language, theme])

  const handleSave = () => {
    i18n.changeLanguage(lang)
    setTheme(themeLocal)
    onClose()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="preferences-title"
        className="relative w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl"
      >
        <div className="mb-6 flex items-center justify-between">
          <h2 id="preferences-title" className="text-lg font-bold text-white">
            {t('preferences.title')}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
            aria-label={t('common.cancel')}
          >
            <span className="text-xl leading-none">×</span>
          </button>
        </div>

        <div className="space-y-6">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-white">
              <Globe className="h-4 w-4 text-slate-400" />
              {t('preferences.language')}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setLang('fr')}
                className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors ${
                  lang === 'fr'
                    ? 'border-violet-500 bg-violet-500/20 text-white'
                    : 'border-slate-600 bg-slate-800 text-slate-300 hover:border-slate-500'
                }`}
              >
                FR Français
              </button>
              <button
                type="button"
                onClick={() => setLang('en')}
                className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors ${
                  lang === 'en'
                    ? 'border-violet-500 bg-violet-500/20 text-white'
                    : 'border-slate-600 bg-slate-800 text-slate-300 hover:border-slate-500'
                }`}
              >
                GB English
              </button>
            </div>
            <div className="mt-3 flex gap-2 rounded-lg border border-amber-800/50 bg-amber-900/20 p-3 text-sm text-amber-200">
              <Info className="h-5 w-5 shrink-0 text-blue-400" />
              <p>{t('preferences.i18nNotice')}</p>
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-white">
              <Sun className="h-4 w-4 text-slate-400" />
              {t('preferences.theme')}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setThemeLocal('light')}
                className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors ${
                  themeLocal === 'light'
                    ? 'border-violet-500 bg-violet-500/20 text-white'
                    : 'border-slate-600 bg-slate-800 text-slate-300 hover:border-slate-500'
                }`}
              >
                <Sun className="h-4 w-4" />
                {t('preferences.light')}
              </button>
              <button
                type="button"
                onClick={() => setThemeLocal('dark')}
                className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors ${
                  themeLocal === 'dark'
                    ? 'border-violet-500 bg-violet-500/20 text-white'
                    : 'border-slate-600 bg-slate-800 text-slate-300 hover:border-slate-500'
                }`}
              >
                <Moon className="h-4 w-4" />
                {t('preferences.dark')}
              </button>
              <button
                type="button"
                onClick={() => setThemeLocal('system')}
                className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors ${
                  themeLocal === 'system'
                    ? 'border-violet-500 bg-violet-500/20 text-white'
                    : 'border-slate-600 bg-slate-800 text-slate-300 hover:border-slate-500'
                }`}
              >
                <Monitor className="h-4 w-4" />
                {t('preferences.system')}
              </button>
            </div>
          </div>
        </div>

        <div className="mt-8 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-700"
          >
            {t('common.cancel')}
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-violet-500"
          >
            <Save className="h-4 w-4" />
            {t('preferences.save')}
          </button>
        </div>
      </div>
    </div>
  )
}
