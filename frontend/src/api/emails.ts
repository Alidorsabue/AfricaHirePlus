import { api } from './axios'
import type { EmailTemplate } from '../types'

export interface EmailRecipient {
  email: string
  first_name: string
  last_name: string
}

export const emailsApi = {
  listTemplates: () => api.get<EmailTemplate[]>('/emails/templates/'),
  getTemplate: (id: number) => api.get<EmailTemplate>(`/emails/templates/${id}/`),
  createTemplate: (data: Partial<EmailTemplate>) =>
    api.post<EmailTemplate>('/emails/templates/', data),
  updateTemplate: (id: number, data: Partial<EmailTemplate>) =>
    api.patch<EmailTemplate>(`/emails/templates/${id}/`, data),
  deleteTemplate: (id: number) => api.delete(`/emails/templates/${id}/`),
  /** Destinataires pour une offre et un type de template (candidats concernés par le type). */
  getRecipients: (jobOfferId: number, templateType: string) =>
    api.get<{ recipients: EmailRecipient[] }>('/emails/recipients/', {
      params: { job_offer_id: jobOfferId, template_type: templateType },
    }),
}
