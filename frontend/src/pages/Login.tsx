import { useState, type ChangeEvent, type FormEvent, type SyntheticEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const { t } = useTranslation()
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const next = searchParams.get('next') || (searchParams.get('from') ? searchParams.get('from') : null) || '/'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const user = await login(username, password)
      if (user?.role === 'candidate') {
        navigate('/candidat', { replace: true })
      } else {
        navigate(next, { replace: true })
      }
    } catch (err: unknown) {
      const apiError = err as {
        message?: string
        response?: {
          status?: number
          data?: {
            detail?: string
            error?: {
              message?: string
              details?: { detail?: string }
            }
          }
        }
      }
      const status = apiError?.response?.status
      const message =
        apiError?.response?.data?.detail ??
        apiError?.response?.data?.error?.details?.detail ??
        apiError?.response?.data?.error?.message

      if (typeof message === 'string' && message.trim()) {
        setError(message)
      } else if (!status) {
        setError("Impossible de contacter l'API (réseau/CORS/URL API).")
      } else if (status === 401) {
        setError('Identifiants incorrects.')
      } else {
        setError('Erreur de connexion. Réessaie dans quelques instants.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center px-4 py-12"
      style={{ backgroundColor: '#1A202C' }}
    >
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <img
            src="/logo/AfricaHire+.png"
            alt="AfricaHire+"
            className="h-40 w-auto object-contain"
            onError={(e: SyntheticEvent<HTMLImageElement>) => { e.currentTarget.style.display = 'none' }}
          />
        </div>

        {/* Title */}
        <h1 className="mb-6 text-center text-xl font-semibold" style={{ color: '#E2E8F0' }}>
          {t('auth.loginTitle')}
        </h1>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg p-3 text-sm text-red-400" style={{ backgroundColor: 'rgba(248,113,113,0.15)' }}>
              {error}
            </div>
          )}
          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: '#E2E8F0' }}>
              {t('auth.username')}
            </label>
            <input
              type="text"
              value={username}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setUsername(e.target.value)}
              placeholder={t('auth.usernamePlaceholder')}
              className="w-full rounded-lg px-4 py-3 placeholder-[#A0AEC0] focus:outline-none focus:ring-2 focus:ring-[#63B3ED]"
              style={{
                backgroundColor: '#2D3748',
                color: '#E2E8F0',
              }}
              required
              autoComplete="username"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: '#E2E8F0' }}>
              {t('auth.password')}
            </label>
            <input
              type="password"
              value={password}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
              placeholder={t('auth.passwordPlaceholder')}
              className="w-full rounded-lg px-4 py-3 placeholder-[#A0AEC0] focus:outline-none focus:ring-2 focus:ring-[#63B3ED]"
              style={{
                backgroundColor: '#2D3748',
                color: '#E2E8F0',
              }}
              required
              autoComplete="current-password"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg py-3 font-medium text-white disabled:opacity-50"
            style={{ backgroundColor: '#6B46C1' }}
          >
            {loading ? t('common.loading') : t('auth.submit')}
          </button>
        </form>

        <p className="mt-6 text-center text-sm" style={{ color: '#E2E8F0' }}>
          {t('auth.noAccount')}{' '}
          <Link to="/register" className="font-medium hover:underline" style={{ color: '#63B3ED' }}>
            {t('auth.register')}
          </Link>
          {' · '}
          <Link to={next ? `/register/candidate?next=${encodeURIComponent(next)}` : '/register/candidate'} className="font-medium hover:underline" style={{ color: '#63B3ED' }}>
            {t('auth.registerCandidate')}
          </Link>
        </p>
      </div>

      {/* Footer slogan */}
      <p className="mt-12 text-center text-sm" style={{ color: '#E2E8F0' }}>
        {t('auth.slogan')}
      </p>
    </div>
  )
}
