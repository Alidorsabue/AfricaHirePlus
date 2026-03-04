import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import { emailsApi } from '../api/emails'
import { jobsApi } from '../api/jobs'
import { unwrapList } from '../api/utils'
import type { EmailTemplate } from '../types'

const TEMPLATE_TYPES = [
  'application_received',
  'application_rejected',
  'shortlist_notification',
  'interview_invitation',
  'offer_letter',
  'test_invitation',
  'reminder',
  'custom',
] as const

export default function EmailTemplates() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<EmailTemplate | null>(null)
  const [creating, setCreating] = useState(false)

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ['emailTemplates'],
    queryFn: async () => unwrapList((await emailsApi.listTemplates()).data),
  })

  const createMutation = useMutation({
    mutationFn: (data: Partial<EmailTemplate>) => emailsApi.createTemplate(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emailTemplates'] })
      setCreating(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<EmailTemplate> }) =>
      emailsApi.updateTemplate(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emailTemplates'] })
      setEditing(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => emailsApi.deleteTemplate(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['emailTemplates'] }),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
      </div>
    )
  }

  return (
    <div>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">{t('emailTemplates.title')}</h1>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <Plus className="h-4 w-4" />
          {t('emailTemplates.new')}
        </button>
      </div>

      {creating && (
        <EmailTemplateForm
          onSave={(data) => createMutation.mutate(data)}
          onCancel={() => setCreating(false)}
          saving={createMutation.isPending}
        />
      )}

      {editing && (
        <EmailTemplateForm
          template={editing}
          onSave={(data) => updateMutation.mutate({ id: editing.id, data })}
          onCancel={() => setEditing(null)}
          saving={updateMutation.isPending}
        />
      )}

      <div className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-600 dark:bg-slate-800">
        {templates.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-500 dark:text-slate-400">{t('emailTemplates.noTemplates')}</div>
        ) : (
          <ul className="divide-y divide-slate-200 dark:divide-slate-600">
            {templates.map((tmpl) => (
              <li
                key={tmpl.id}
                className="flex flex-col gap-2 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-medium text-slate-800 dark:text-slate-100">{tmpl.name}</p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{tmpl.subject}</p>
                  <span className="mt-1 inline-block rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                    {tmpl.template_type}
                  </span>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setEditing(tmpl)}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                  >
                    <Pencil className="h-4 w-4" />
                    Modifier
                  </button>
                  <button
                    type="button"
                    onClick={() => window.confirm(t('common.delete')) && deleteMutation.mutate(tmpl.id)}
                    className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50"
                  >
                    <Trash2 className="h-4 w-4" />
                    {t('common.delete')}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function EmailTemplateForm({
  template,
  onSave,
  onCancel,
  saving,
}: {
  template?: EmailTemplate
  onSave: (data: Partial<EmailTemplate>) => void
  onCancel: () => void
  saving: boolean
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState({
    name: template?.name ?? '',
    template_type: template?.template_type ?? 'custom',
    subject: template?.subject ?? '',
    body_html: template?.body_html ?? '',
    body_text: template?.body_text ?? '',
    is_active: template?.is_active ?? true,
  })
  const [selectedJobOfferId, setSelectedJobOfferId] = useState<string>('')

  const { data: jobsData } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => (await jobsApi.list()).data,
  })
  const jobOffers = unwrapList(jobsData)

  const jobOfferIdNum = selectedJobOfferId ? parseInt(selectedJobOfferId, 10) : null
  const { data: recipientsData } = useQuery({
    queryKey: ['emailRecipients', jobOfferIdNum, form.template_type],
    queryFn: () =>
      emailsApi.getRecipients(jobOfferIdNum!, form.template_type).then((r) => r.data),
    enabled: !!jobOfferIdNum && !!form.template_type,
  })
  const recipients = recipientsData?.recipients ?? []

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave(form)
  }

  const inputBase =
    'w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 placeholder:text-slate-500 focus:border-teal-500 focus:outline-none dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:placeholder:text-slate-400'

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-600 dark:bg-slate-800"
    >
      <h2 className="mb-4 font-semibold text-slate-800 dark:text-slate-100">
        {template ? t('emailTemplates.save') : t('emailTemplates.new')}
      </h2>
      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('emailTemplates.offer')}</label>
          <select
            value={selectedJobOfferId}
            onChange={(e) => setSelectedJobOfferId(e.target.value)}
            className={inputBase}
          >
            <option value="">{t('emailTemplates.offerPlaceholder')}</option>
            {jobOffers.map((job) => (
              <option key={job.id} value={String(job.id)}>
                {job.title}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('emailTemplates.name')}</label>
          <input
            value={form.name}
            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            className={inputBase}
            placeholder={t('emailTemplates.namePlaceholder')}
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('emailTemplates.type')}</label>
          <select
            value={form.template_type}
            onChange={(e) => setForm((p) => ({ ...p, template_type: e.target.value }))}
            className={inputBase}
          >
            {TEMPLATE_TYPES.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('emailTemplates.sentTo')}</label>
          <p className="mb-2 text-xs text-slate-600 dark:text-slate-300">{t('emailTemplates.sentToHint')}</p>
          {selectedJobOfferId ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200">
              {recipients.length === 0 ? (
                <span className="text-slate-600 dark:text-slate-400">{t('emailTemplates.noRecipients')}</span>
              ) : (
                <ul className="list-inside list-disc space-y-0.5">
                  {recipients.map((r) => (
                    <li key={r.email}>
                      {r.first_name || r.last_name
                        ? `${r.first_name} ${r.last_name}`.trim() + ` <${r.email}>`
                        : r.email}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <span className="text-sm text-slate-600 dark:text-slate-300">{t('emailTemplates.sentToHint')}</span>
          )}
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('emailTemplates.subject')}</label>
          <input
            value={form.subject}
            onChange={(e) => setForm((p) => ({ ...p, subject: e.target.value }))}
            className={inputBase}
            placeholder={t('emailTemplates.subjectPlaceholder')}
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('emailTemplates.bodyHtml')}</label>
          <textarea
            value={form.body_html}
            onChange={(e) => setForm((p) => ({ ...p, body_html: e.target.value }))}
            rows={6}
            placeholder={t('emailTemplates.bodyPlaceholder')}
            className={`${inputBase} font-mono text-sm`}
          />
        </div>
        <div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
              className="rounded border-slate-300 text-teal-600 dark:border-slate-600 dark:bg-slate-700"
            />
            <span className="text-sm text-slate-700 dark:text-slate-200">{t('emailTemplates.active')}</span>
          </label>
        </div>
      </div>
      <div className="mt-6 flex gap-4">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-teal-600 px-6 py-2.5 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {saving ? t('common.loading') : t('emailTemplates.save')}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-slate-300 px-6 py-2.5 font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
        >
          {t('common.cancel')}
        </button>
      </div>
    </form>
  )
}
