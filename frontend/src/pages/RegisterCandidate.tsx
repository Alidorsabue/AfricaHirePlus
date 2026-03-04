import { useState, useEffect } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { authApi } from '../api/auth'
import { useAuth } from '../contexts/AuthContext'

const inputClass =
  'w-full rounded-lg px-4 py-2.5 placeholder-[#A0AEC0] focus:outline-none focus:ring-2 focus:ring-[#63B3ED]'
const inputStyle = { backgroundColor: '#2D3748', color: '#E2E8F0' }
const labelStyle = { color: '#E2E8F0' }

export default function RegisterCandidate() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, login } = useAuth()
  const [searchParams] = useSearchParams()
  const next = searchParams.get('next') || '/'

  useEffect(() => {
    if (user) {
      if (user.role === 'candidate') navigate('/candidat', { replace: true })
      else navigate(next, { replace: true })
    }
  }, [user, next, navigate])

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    email: '',
    password: '',
    password_confirm: '',
    first_name: '',
    last_name: '',
    phone: '',
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((p) => ({ ...p, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (form.password !== form.password_confirm) {
      setError(t('auth.passwordMismatch'))
      return
    }
    setLoading(true)
    try {
      await authApi.registerCandidate({
        email: form.email,
        password: form.password,
        password_confirm: form.password_confirm,
        first_name: form.first_name,
        last_name: form.last_name,
        phone: form.phone || undefined,
      })
      const loggedInUser = await login(form.email, form.password)
      if (loggedInUser?.role === 'candidate') {
        navigate('/candidat', { replace: true })
      } else {
        navigate(next, { replace: true })
      }
    } catch (err: unknown) {
      const data = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: Record<string, string | string[]> } }).response?.data
        : null
      const msg = data && typeof data === 'object'
        ? (Array.isArray(data.email) ? data.email[0] : data.email) ||
          (Array.isArray(data.detail) ? data.detail[0] : data.detail) ||
          JSON.stringify(data)
        : t('auth.registerError')
      setError(typeof msg === 'string' ? msg : 'Erreur')
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
        <div className="mb-6 flex justify-center">
          <img
            src="/logo/AfricaHire+.png"
            alt="AfricaHire+"
            className="h-32 w-auto object-contain"
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
        </div>

        <h1 className="mb-6 text-center text-xl font-semibold" style={{ color: '#E2E8F0' }}>
          {t('auth.registerCandidateTitle')}
        </h1>
        <p className="mb-6 text-center text-sm" style={{ color: '#A0AEC0' }}>
          {t('auth.registerCandidateHint')}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg p-3 text-sm text-red-400" style={{ backgroundColor: 'rgba(248,113,113,0.15)' }}>
              {error}
            </div>
          )}
          <div>
            <label className="mb-1 block text-sm font-medium" style={labelStyle}>{t('auth.email')} *</label>
            <input
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              required
              className={inputClass}
              style={inputStyle}
              autoComplete="email"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium" style={labelStyle}>{t('auth.firstName')} *</label>
              <input
                type="text"
                name="first_name"
                value={form.first_name}
                onChange={handleChange}
                required
                className={inputClass}
                style={inputStyle}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium" style={labelStyle}>{t('auth.lastName')} *</label>
              <input
                type="text"
                name="last_name"
                value={form.last_name}
                onChange={handleChange}
                required
                className={inputClass}
                style={inputStyle}
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium" style={labelStyle}>{t('publicJob.phone')}</label>
            <input
              type="tel"
              name="phone"
              value={form.phone}
              onChange={handleChange}
              className={inputClass}
              style={inputStyle}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium" style={labelStyle}>{t('auth.password')} *</label>
            <input
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              required
              minLength={8}
              className={inputClass}
              style={inputStyle}
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium" style={labelStyle}>{t('auth.confirmPassword')} *</label>
            <input
              type="password"
              name="password_confirm"
              value={form.password_confirm}
              onChange={handleChange}
              required
              className={inputClass}
              style={inputStyle}
              autoComplete="new-password"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg py-3 font-medium text-white disabled:opacity-50"
            style={{ backgroundColor: '#6B46C1' }}
          >
            {loading ? t('common.loading') : t('auth.createAccount')}
          </button>
        </form>

        <p className="mt-6 text-center text-sm" style={{ color: '#E2E8F0' }}>
          {t('auth.hasAccount')}{' '}
          <Link to={next !== '/' ? `/login?next=${encodeURIComponent(next)}` : '/login'} className="font-medium hover:underline" style={{ color: '#63B3ED' }}>
            {t('nav.login')}
          </Link>
        </p>
      </div>
    </div>
  )
}
