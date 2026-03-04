import { api } from './axios'
import type { Test, Question, CandidateTestResult } from '../types'

export interface TestWritePayload {
  title: string
  description?: string
  test_type?: string
  duration_minutes?: number | null
  passing_score?: string | null
  is_active?: boolean
  company?: number
  job_offer?: number | null
  access_code?: string | null
  sections?: Array<{ title: string; order: number }>
  questions?: Array<Partial<Question> & { section_index?: number | null }>
}

export const testsApi = {
  list: () => api.get<Test[]>('/tests/'),
  get: (id: number) => api.get<Test>(`/tests/${id}/`),
  create: (data: TestWritePayload) => api.post<Test>('/tests/', data),
  update: (id: number, data: TestWritePayload) => api.patch<Test>(`/tests/${id}/`, data),
  delete: (id: number) => api.delete(`/tests/${id}/`),
  uploadQuestionAttachment: (testId: number, questionId: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<{ attachment: string; question_id: number }>(
      `/tests/${testId}/questions/${questionId}/attachment/`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
  },
  startSession: (applicationId: number, testId: number) =>
    api.post('/tests/start-session/', {
      application_id: applicationId,
      test_id: testId,
    }),
  autoSave: (applicationId: number, testId: number, answers: Record<string, unknown>) =>
    api.post('/tests/auto-save/', {
      application_id: applicationId,
      test_id: testId,
      answers,
    }),
  uploadFile: (applicationId: number, testId: number, questionId: number, file: File) => {
    const formData = new FormData()
    formData.append('application_id', String(applicationId))
    formData.append('test_id', String(testId))
    formData.append('question_id', String(questionId))
    formData.append('file', file)
    return api.post('/tests/upload-file/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  tabSwitch: (applicationId: number, testId: number) =>
    api.post('/tests/tab-switch/', {
      application_id: applicationId,
      test_id: testId,
    }),
  submitAnswers: (applicationId: number, testId: number, answers: Record<string, unknown>) =>
    api.post('/tests/submit-answers/', {
      application_id: applicationId,
      test_id: testId,
      answers,
    }),
  checkAccess: (email: string, code: string, testId: number) =>
    api.post<{ application_id: number; test_id: number }>('/tests/check-access/', {
      email,
      code,
      test_id: testId,
    }),
  /** Candidat : tests disponibles (par candidature) pour passer un test */
  availableForCandidate: () =>
    api.get<Array<{
      application_id: number
      job_title: string | null
      test_id: number
      test_title: string
      duration_minutes: number | null
      session_id: number | null
      status: string
      is_completed: boolean
    }>>('/tests/available-for-candidate/'),
  /** Candidat : sessions déjà démarrées ou soumises */
  mySessions: () => api.get<Array<{ id: number; application_id: number; test_id: number; test_title: string; job_title: string | null; status: string; is_completed: boolean }>>('/tests/my-sessions/'),
  results: {
    list: () => api.get<CandidateTestResult[]>('/tests/results/'),
    get: (id: number) => api.get<CandidateTestResult>(`/tests/results/${id}/`),
    report: (id: number) => api.get(`/tests/results/${id}/report/`),
  },
  exportResultsExcel: () =>
    api.get('/tests/export/results/xlsx/', { responseType: 'blob' }),
}

