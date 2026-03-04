import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { testsApi } from '../api/tests'

export default function TestAccess() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialCode = searchParams.get('code') || ''
  const initialTestId = searchParams.get('test_id') || searchParams.get('testId') || ''

  const [email, setEmail] = useState('')
  const [code, setCode] = useState(initialCode)
  const [testId, setTestId] = useState(initialTestId)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (initialCode) setCode(initialCode)
    if (initialTestId) setTestId(initialTestId)
  }, [initialCode, initialTestId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!email.trim() || !code.trim() || !testId) {
      setError(t('candidat.testAccessMissing') || 'Veuillez renseigner email, code et test.')
      return
    }
    setLoading(true)
    try {
      const { data } = await testsApi.checkAccess(email.trim(), code.trim(), Number(testId))
      navigate(`/candidat/tests/${data.test_id}?applicationId=${data.application_id}`)
    } catch (err: any) {
      const msg =
        err?.response?.data?.error?.details?.detail ||
        err?.response?.data?.detail ||
        t('candidat.testAccessDenied') ||
        'Accès refusé pour ce test.'
      setError(String(msg))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        {t('candidat.testAccessTitle') || 'Accès au test technique'}
      </h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        {t('candidat.testAccessHint') ||
          "Saisissez votre adresse email et le code d'accès reçu dans l'email d'invitation pour démarrer le test."}
      </p>
      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
            {error}
          </div>
        )}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
            {t('auth.email') || 'Email'}
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
            {t('candidat.testAccessCode') || "Code d'accès"}
          </label>
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
            {t('candidat.testAccessTestId') || 'ID du test'}
          </label>
          <input
            type="number"
            value={testId}
            onChange={(e) => setTestId(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            required
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {loading ? t('common.loading') || 'Chargement...' : t('candidat.takeTest') || 'Passer le test'}
        </button>
      </form>
    </div>
  )
}

