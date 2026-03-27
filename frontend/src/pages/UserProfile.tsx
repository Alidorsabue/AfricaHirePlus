/**
 * Page Profil utilisateur : affichage, édition des infos (auth/me) et changement de mot de passe.
 * Accessible via le menu utilisateur (Profil) pour tous les rôles.
 */
import { useState, useEffect, type FormEvent, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { User, ArrowLeft } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { authApi } from '../api/auth'
import { getMediaBaseUrl } from '../api/env'
import { companiesApi } from '../api/companies'
import { unwrapList } from '../api/utils'
import type { User as UserType, Company } from '../types'

const roleKeys: Record<string, string> = {
  super_admin: 'user.roleAdmin',
  admin: 'user.roleAdmin',
  recruiter: 'user.roleRecruiter',
  candidate: 'user.roleCandidate',
}

type PasswordForm = {
  current_password: string
  new_password: string
  new_password_confirm: string
}

function formatDate(s: string) {
  try {
    return new Date(s).toLocaleDateString(undefined, {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
  } catch {
    return s
  }
}

export default function UserProfile() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user: authUser, refreshUser } = useAuth()
  const queryClient = useQueryClient()

  const { data: user, isLoading } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => (await authApi.me()).data,
    initialData: authUser ?? undefined,
  })

  const companyId = user?.company != null ? Number(user.company) : null
  const { data: companies = [] } = useQuery({
    queryKey: ['companies'],
    queryFn: async () => unwrapList((await companiesApi.list()).data),
    enabled: !!companyId,
  })
  const company = companies.find((c: Company) => c.id === companyId)

  const [form, setForm] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    phone: '',
  })
  const [avatarFile, setAvatarFile] = useState<File | null>(null)
  const [passwordForm, setPasswordForm] = useState<PasswordForm>({
    current_password: '',
    new_password: '',
    new_password_confirm: '',
  })

  useEffect(() => {
    if (user) {
      setForm({
        username: user.username ?? '',
        email: user.email ?? '',
        first_name: user.first_name ?? '',
        last_name: user.last_name ?? '',
        phone: user.phone ?? '',
      })
    }
  }, [user])

  const updateMutation = useMutation({
    mutationFn: async (payload: Omit<Partial<UserType>, 'avatar'> & { avatar?: File }) => {
      if (payload.avatar) {
        const fd = new FormData()
        fd.append('username', form.username)
        fd.append('email', form.email)
        fd.append('first_name', form.first_name)
        fd.append('last_name', form.last_name)
        fd.append('phone', form.phone)
        fd.append('avatar', payload.avatar)
        return (await authApi.updateMe(fd)).data
      }
      return (await authApi.updateMe(payload)).data
    },
    onSuccess: (data: UserType) => {
      queryClient.setQueryData(['auth', 'me'], data)
      refreshUser()
    },
  })

  const passwordMutation = useMutation({
    mutationFn: (data: typeof passwordForm) => authApi.changePassword(data),
    onSuccess: () => {
      setPasswordForm({ current_password: '', new_password: '', new_password_confirm: '' })
    },
  })

  const handleChange = (
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target
    setForm((p: typeof form) => ({ ...p, [name]: value }))
  }

  const handleSubmitProfile = (e: FormEvent) => {
    e.preventDefault()
    if (avatarFile) {
      updateMutation.mutate({ ...form, avatar: avatarFile })
      setAvatarFile(null)
    } else {
      updateMutation.mutate(form)
    }
  }

  const handleSubmitPassword = (e: FormEvent) => {
    e.preventDefault()
    passwordMutation.mutate(passwordForm)
  }

  const mediaBase = getMediaBaseUrl()
  const avatarUrl = user?.avatar
    ? user.avatar.startsWith('http')
      ? user.avatar
      : `${mediaBase}${user.avatar.startsWith('/') ? '' : '/'}${user.avatar}`
    : null

  if (isLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <p className="text-slate-600 dark:text-slate-400">{t('profilePage.loading')}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex h-14 max-w-3xl items-center gap-4 px-4">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 rounded-lg px-2 py-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <ArrowLeft className="h-5 w-5" />
            {t('profilePage.back')}
          </button>
          <h1 className="text-lg font-semibold text-slate-800 dark:text-slate-100">
            {t('profilePage.title')}
          </h1>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8">
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
          {t('profilePage.hint')}
        </p>

        {/* Infos en lecture seule */}
        <section className="mb-8 rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800/50">
          <div className="flex flex-col items-start gap-6 sm:flex-row sm:items-center">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-full bg-violet-100 dark:bg-violet-900/30">
              {avatarFile ? (
                <img
                  src={URL.createObjectURL(avatarFile)}
                  alt=""
                  className="h-full w-full object-cover"
                />
              ) : avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt=""
                  className="h-full w-full object-cover"
                />
              ) : (
                <User className="h-10 w-10 text-violet-600 dark:text-violet-400" />
              )}
            </div>
            <div className="min-w-0 flex-1 space-y-1">
              <p className="font-medium text-slate-800 dark:text-slate-100">
                {user.first_name || user.last_name
                  ? `${user.first_name} ${user.last_name}`.trim()
                  : user.username}
              </p>
              <p className="truncate text-sm text-slate-500 dark:text-slate-400">
                {user.email}
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {t('profilePage.role')} : {t(roleKeys[user.role] ?? 'user.roleRecruiter')}
              </p>
              {company && (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('profilePage.company')} : {company.name}
                </p>
              )}
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {t('profilePage.dateJoined')} : {formatDate(user.date_joined)}
              </p>
            </div>
          </div>
        </section>

        {/* Formulaire d'édition */}
        <section className="mb-8 rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800/50">
          <h2 className="mb-4 text-lg font-medium text-slate-800 dark:text-slate-100">
            {t('profilePage.editInfo')}
          </h2>
          <form onSubmit={handleSubmitProfile} className="space-y-4">
            {updateMutation.isSuccess && (
              <p className="rounded-lg bg-teal-50 p-2 text-sm text-teal-700 dark:bg-teal-900/30 dark:text-teal-300">
                {t('profilePage.profileUpdated')}
              </p>
            )}
            {updateMutation.error && (
              <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
                {(updateMutation.error as Error).message}
              </p>
            )}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                {t('profilePage.username')}
              </label>
              <input
                type="text"
                name="username"
                value={form.username}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                {t('profilePage.email')}
              </label>
              <input
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                  {t('profilePage.firstName')}
                </label>
                <input
                  type="text"
                  name="first_name"
                  value={form.first_name}
                  onChange={handleChange}
                  className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                  {t('profilePage.lastName')}
                </label>
                <input
                  type="text"
                  name="last_name"
                  value={form.last_name}
                  onChange={handleChange}
                  className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                {t('profilePage.phone')}
              </label>
              <input
                type="text"
                name="phone"
                value={form.phone}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                {t('profilePage.avatar')}
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setAvatarFile(e.target.files?.[0] ?? null)}
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 file:mr-4 file:rounded file:border-0 file:bg-violet-100 file:px-3 file:py-1.5 file:text-violet-700 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:file:bg-violet-900/30 dark:file:text-violet-300"
              />
            </div>
            <button
              type="submit"
              disabled={updateMutation.isPending}
              className="rounded-lg bg-teal-600 px-6 py-2.5 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            >
              {updateMutation.isPending ? t('profilePage.loading') : t('profilePage.save')}
            </button>
          </form>
        </section>

        {/* Changement de mot de passe */}
        <section className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800/50">
          <h2 className="mb-4 text-lg font-medium text-slate-800 dark:text-slate-100">
            {t('profilePage.changePassword')}
          </h2>
          <form onSubmit={handleSubmitPassword} className="space-y-4">
            {passwordMutation.isSuccess && (
              <p className="rounded-lg bg-teal-50 p-2 text-sm text-teal-700 dark:bg-teal-900/30 dark:text-teal-300">
                {t('profilePage.passwordUpdated')}
              </p>
            )}
            {passwordMutation.error && (
              <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
                {(() => {
                  const err = passwordMutation.error as { response?: { data?: Record<string, string[]> } }
                  const d = err.response?.data
                  if (d?.current_password?.[0]) return d.current_password[0]
                  if (d?.new_password_confirm?.[0]) return d.new_password_confirm[0]
                  return (passwordMutation.error as Error).message
                })()}
              </p>
            )}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                {t('profilePage.currentPassword')}
              </label>
              <input
                type="password"
                value={passwordForm.current_password}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setPasswordForm((p: PasswordForm) => ({ ...p, current_password: e.target.value }))
                }
                required
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                {t('profilePage.newPassword')}
              </label>
              <input
                type="password"
                value={passwordForm.new_password}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setPasswordForm((p: PasswordForm) => ({ ...p, new_password: e.target.value }))
                }
                required
                minLength={8}
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                {t('profilePage.newPasswordConfirm')}
              </label>
              <input
                type="password"
                value={passwordForm.new_password_confirm}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setPasswordForm((p: PasswordForm) => ({ ...p, new_password_confirm: e.target.value }))
                }
                required
                minLength={8}
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              />
            </div>
            <button
              type="submit"
              disabled={passwordMutation.isPending}
              className="rounded-lg bg-violet-600 px-6 py-2.5 font-medium text-white hover:bg-violet-700 disabled:opacity-50"
            >
              {passwordMutation.isPending
                ? t('profilePage.loading')
                : t('profilePage.updatePassword')}
            </button>
          </form>
        </section>
      </main>
    </div>
  )
}
