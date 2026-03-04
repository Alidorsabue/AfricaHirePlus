/**
 * Création / édition d'un test et de ses questions (équivalent admin Django).
 */
import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Upload, FileText } from 'lucide-react'
import { jobsApi } from '../api/jobs'
import { useAuth } from '../contexts/AuthContext'
import { testsApi, type TestWritePayload } from '../api/tests'
import type { Test, Question } from '../types'

const TEST_TYPES = [
  { value: 'technical', labelKey: 'test.typeTechnical' },
  { value: 'personality', labelKey: 'test.typePersonality' },
  { value: 'language', labelKey: 'test.typeLanguage' },
  { value: 'case_study', labelKey: 'test.typeCaseStudy' },
  { value: 'other', labelKey: 'test.typeOther' },
] as const

const QUESTION_TYPES = [
  { value: 'single_choice', labelKey: 'test.qSingleChoice' },
  { value: 'multiple_choice', labelKey: 'test.qMultipleChoice' },
  { value: 'text', labelKey: 'test.qText' },
  { value: 'number', labelKey: 'test.qNumber' },
  { value: 'boolean', labelKey: 'test.qBoolean' },
  { value: 'file_upload', labelKey: 'test.qFileUpload' },
  { value: 'code', labelKey: 'test.qCode' },
] as const

interface SectionForm {
  title: string
  order: number
}

interface QuestionForm {
  text: string
  question_type: string
  options: Array<{ id: string; label: string; correct?: boolean }>
  correct_answer: string | string[] | number | null
  points: number
  order: number
  section_index: number | null
  code_language?: string
  starter_code?: string
  attachmentFile?: File | null
  attachmentUrl?: string | null
}

export default function TestForm() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const isNew = !id
  const testId = id ? parseInt(id, 10) : 0

  const [form, setForm] = useState({
    title: '',
    description: '',
    test_type: 'technical',
    duration_minutes: '' as string | number,
    passing_score: '' as string | number,
    is_active: true,
  })
  const [sections, setSections] = useState<SectionForm[]>([])
  const [questions, setQuestions] = useState<QuestionForm[]>([])
  const [selectedJobOfferId, setSelectedJobOfferId] = useState<string>('')

  const { data: jobsData } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list(),
  })
  const jobOffers = Array.isArray(jobsData?.data) ? jobsData.data : []

  const { data: testRes, isLoading } = useQuery({
    queryKey: ['test', testId],
    queryFn: () => testsApi.get(testId),
    enabled: !isNew && testId > 0,
  })

  // En mode édition : charger le test et ses questions dès que la réponse API est disponible
  useEffect(() => {
    if (isNew || !testRes?.data) return
    const payload = testRes.data as unknown
    if (typeof (payload as { id?: unknown })?.id !== 'number') return
    const t = payload as Test
    setForm({
      title: t.title ?? '',
      description: t.description ?? '',
      test_type: t.test_type ?? 'technical',
      duration_minutes: t.duration_minutes ?? '',
      passing_score: t.passing_score ?? '',
      is_active: t.is_active ?? true,
    })
    const jobOfferField = (t as any).job_offer
    if (typeof jobOfferField === 'number') {
      setSelectedJobOfferId(String(jobOfferField))
    } else if (jobOfferField && typeof jobOfferField === 'object' && (jobOfferField as any).id) {
      setSelectedJobOfferId(String((jobOfferField as any).id))
    } else {
      setSelectedJobOfferId('')
    }
    const rawSections = (t as any).sections
    const sectionsList = Array.isArray(rawSections) ? rawSections : []
    setSections(
      sectionsList.length
        ? sectionsList.map((s: { id?: number; title?: string; order?: number }, i: number) => ({
            title: String(s.title ?? ''),
            order: Number(s.order) ?? i,
          }))
        : []
    )
    const rawQuestions = t.questions
    const questionsList = Array.isArray(rawQuestions) ? rawQuestions : []
    setQuestions(
      questionsList.map((q: Question | Record<string, unknown>, i: number) => {
        const qSectionId = (q as any).section
        const sectionIndex =
          typeof qSectionId === 'number' && sectionsList.length
            ? sectionsList.findIndex((s: { id?: number }) => s.id === qSectionId)
            : -1
        const opts = Array.isArray((q as Question).options) ? (q as Question).options : []
        const normalizedOptions = opts.map((o: Record<string, unknown> | { id: string; label: string; correct?: boolean }, j: number) => ({
          id: typeof (o as any).id === 'string' ? (o as any).id : String((o as any).id ?? `opt-${j}`),
          label: String((o as any).label ?? (o as any).text ?? ''),
          correct: Boolean((o as any).correct),
        }))
        return {
          text: String((q as Question).text ?? ''),
          question_type: String((q as Question).question_type ?? 'single_choice'),
          options: normalizedOptions.length ? normalizedOptions : [{ id: 'a', label: '', correct: false }, { id: 'b', label: '', correct: false }],
          correct_answer: (q as Question).correct_answer ?? null,
          points: Number((q as Question).points) || 1,
          order: Number((q as Question).order) ?? i,
          section_index: sectionIndex >= 0 ? sectionIndex : null,
          code_language: String((q as any).code_language ?? ''),
          starter_code: String((q as any).starter_code ?? ''),
          attachmentFile: null as File | null,
          attachmentUrl: (q as any).attachment ?? null,
        }
      })
    )
  }, [isNew, testRes?.data])

  const createMutation = useMutation({
    mutationFn: (data: TestWritePayload) => testsApi.create(data),
  })

  const updateMutation = useMutation({
    mutationFn: (data: TestWritePayload) => testsApi.update(testId, data),
  })

  const buildPayload = (): TestWritePayload => {
    const payload: TestWritePayload = {
      title: form.title,
      description: form.description || undefined,
      test_type: form.test_type,
      duration_minutes: form.duration_minutes === '' ? null : Number(form.duration_minutes),
      passing_score: form.passing_score === '' ? null : String(form.passing_score),
      is_active: form.is_active,
      sections: sections.length ? sections.map((s, i) => ({ title: s.title, order: s.order ?? i })) : undefined,
      questions: questions.map((q, i) => ({
        text: q.text,
        question_type: q.question_type,
        options: q.options,
        correct_answer: q.correct_answer,
        points: q.points,
        order: i,
        section_index: q.section_index,
        code_language: q.code_language,
        starter_code: q.starter_code,
      })),
    }
    if (isNew && user?.company != null) payload.company = Number(user.company)
    if (selectedJobOfferId) {
      payload.job_offer = Number(selectedJobOfferId)
    }
    return payload
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.title.trim()) return
    const payload = buildPayload()
    try {
      const response = isNew
        ? await createMutation.mutateAsync(payload)
        : await updateMutation.mutateAsync(payload)
      const test = (response as { data?: Test })?.data
      if (test?.questions?.length) {
        const ids = test.questions.map((q: { id: number }) => q.id)
        for (let i = 0; i < questions.length; i++) {
          const file = questions[i].question_type === 'file_upload' ? questions[i].attachmentFile : null
          if (file && ids[i] != null) {
            const testId = test.id
            await testsApi.uploadQuestionAttachment(testId, ids[i], file)
          }
        }
      }
      queryClient.invalidateQueries({ queryKey: ['tests'] })
      if (!isNew) queryClient.invalidateQueries({ queryKey: ['test', testId] })
      navigate('/tests')
    } catch {
      // Error already handled by mutation
    }
  }

  const addSection = () => {
    setSections((prev) => [...prev, { title: '', order: prev.length }])
  }
  const removeSection = (idx: number) => {
    setSections((prev) => prev.filter((_, i) => i !== idx))
    setQuestions((prev) =>
      prev.map((q) => {
        if (q.section_index === null) return q
        if (q.section_index === idx) return { ...q, section_index: null }
        if (q.section_index > idx) return { ...q, section_index: q.section_index - 1 }
        return q
      })
    )
  }
  const updateSection = (idx: number, field: keyof SectionForm, value: string | number) => {
    setSections((prev) => prev.map((s, i) => (i === idx ? { ...s, [field]: value } : s)))
  }

  const addQuestion = () => {
    setQuestions((prev) => [
      ...prev,
      {
        text: '',
        question_type: 'single_choice',
        options: [{ id: 'a', label: '', correct: false }, { id: 'b', label: '', correct: false }],
        correct_answer: null,
        points: 1,
        order: questions.length,
        section_index: null,
        attachmentFile: null,
        attachmentUrl: null,
      },
    ])
  }

  const removeQuestion = (index: number) => {
    setQuestions((prev) => prev.filter((_, i) => i !== index))
  }

  const updateQuestion = (index: number, field: keyof QuestionForm, value: QuestionForm[keyof QuestionForm]) => {
    setQuestions((prev) => {
      const next = prev.map((q, i) => (i === index ? { ...q, [field]: value } : q))
      if (field === 'question_type' && (value === 'single_choice' || value === 'multiple_choice')) {
        const q = next[index]
        if (!q.options?.length) {
          next[index] = {
            ...q,
            options: [
              { id: 'a', label: '', correct: false },
              { id: 'b', label: '', correct: false },
            ],
            correct_answer: value === 'multiple_choice' ? [] : null,
          }
        }
      }
      return next
    })
  }

  const updateQuestionOption = (
    qIdx: number,
    optionIdx: number,
    field: 'label' | 'correct',
    value: string | boolean
  ) => {
    setQuestions((prev) => {
      const q = prev[qIdx]
      const options = [...(q.options || [])]
      if (optionIdx >= options.length) return prev
      const opt = { ...options[optionIdx], [field]: value }
      if (field === 'correct' && value === true && q.question_type === 'single_choice') {
        options.forEach((o, i) => (options[i] = { ...o, correct: i === optionIdx }))
        options[optionIdx] = opt
        const correct_answer = opt.id
        return prev.map((qu, i) => (i === qIdx ? { ...qu, options, correct_answer } : qu))
      }
      options[optionIdx] = opt
      if (field === 'correct') {
        const correctIds = options.filter((o) => o.correct).map((o) => o.id)
        const correct_answer = q.question_type === 'multiple_choice' ? correctIds : correctIds[0] ?? null
        return prev.map((qu, i) => (i === qIdx ? { ...qu, options, correct_answer } : qu))
      }
      return prev.map((qu, i) => (i === qIdx ? { ...qu, options } : qu))
    })
  }

  const addQuestionOption = (qIdx: number) => {
    setQuestions((prev) => {
      const q = prev[qIdx]
      const ids = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
      const used = new Set((q.options || []).map((o) => o.id))
      const nextId = ids.find((id) => !used.has(id)) ?? `opt-${Date.now()}`
      const options = [...(q.options || []), { id: nextId, label: '', correct: false }]
      return prev.map((qu, i) => (i === qIdx ? { ...qu, options } : qu))
    })
  }

  const removeQuestionOption = (qIdx: number, optionIdx: number) => {
    setQuestions((prev) => {
      const q = prev[qIdx]
      const options = (q.options || []).filter((_, i) => i !== optionIdx)
      if (options.length < 2) return prev
      const correctIds = options.filter((o) => o.correct).map((o) => o.id)
      const correct_answer =
        q.question_type === 'multiple_choice' ? correctIds : (correctIds[0] ?? null)
      return prev.map((qu, i) => (i === qIdx ? { ...qu, options, correct_answer } : qu))
    })
  }

  if (!isNew && isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
      </div>
    )
  }

  const mutating = createMutation.isPending || updateMutation.isPending
  const error = createMutation.error || updateMutation.error

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">
        {isNew ? t('test.newTest') : t('test.editTest')}
      </h1>
      <form onSubmit={handleSubmit} className="mt-6 space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800/50">
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
            {(error as Error).message}
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('test.title')} *</label>
            <input
              value={form.title}
              onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
              required
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
              {t('test.jobOffer')}
            </label>
            <select
              value={selectedJobOfferId}
              onChange={(e) => setSelectedJobOfferId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              <option value="">{t('test.jobOfferPlaceholder')}</option>
              {jobOffers.map((job: any) => (
                <option key={job.id} value={String(job.id)}>
                  {job.title}
                </option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('test.description')}</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
              rows={2}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('test.type')}</label>
            <select
              value={form.test_type}
              onChange={(e) => setForm((p) => ({ ...p, test_type: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            >
              {TEST_TYPES.map((opt) => (
                <option key={opt.value} value={opt.value}>{t(opt.labelKey)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('test.duration')} (min)</label>
            <input
              type="number"
              min="0"
              value={form.duration_minutes}
              onChange={(e) => setForm((p) => ({ ...p, duration_minutes: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{t('test.passingScore')}</label>
            <input
              type="text"
              value={form.passing_score}
              onChange={(e) => setForm((p) => ({ ...p, passing_score: e.target.value }))}
              placeholder="60"
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
              className="rounded border-slate-300 text-teal-600 dark:border-slate-600 dark:bg-slate-700 dark:text-teal-400"
            />
            <span className="text-sm text-slate-700 dark:text-slate-200">{t('test.isActive')}</span>
          </div>
        </div>

        <div className="border-t border-slate-200 pt-6 dark:border-slate-600">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">{t('test.sections') || 'Sections'}</h2>
            <button type="button" onClick={addSection} className="inline-flex items-center gap-1 rounded-lg border border-teal-500 px-3 py-1.5 text-sm font-medium text-teal-600 hover:bg-teal-50 dark:border-teal-400 dark:text-teal-400 dark:hover:bg-teal-900/30">
              <Plus className="h-4 w-4" />
              {t('test.addSection') || 'Ajouter une section'}
            </button>
          </div>
          {sections.length > 0 ? (
            <ul className="mb-6 space-y-2">
              {sections.map((sec, idx) => (
                <li key={idx} className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50/50 p-2 dark:border-slate-600 dark:bg-slate-800/30">
                  <span className="text-sm font-medium text-slate-500 dark:text-slate-400">{idx + 1}.</span>
                  <input
                    value={sec.title}
                    onChange={(e) => updateSection(idx, 'title', e.target.value)}
                    placeholder={t('test.sectionTitle') || 'Titre de la section'}
                    className="flex-1 rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                  />
                  <button type="button" onClick={() => removeSection(idx)} className="rounded p-1 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
              {t('test.sectionsHint') || 'Les sections permettent de regrouper les questions et d\'afficher le score par section dans les rapports recruteur.'}
            </p>
          )}

          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">{t('test.questions')}</h2>
            <button type="button" onClick={addQuestion} className="inline-flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700">
              <Plus className="h-4 w-4" />
              {t('test.addQuestion')}
            </button>
          </div>
          {questions.length === 0 ? (
            <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 py-4 text-center text-sm text-slate-500 dark:border-slate-600 dark:bg-slate-800/50 dark:text-slate-400">
              {t('test.noQuestions')}
            </p>
          ) : (
            <ul className="space-y-4">
              {questions.map((q, idx) => (
                <li key={idx} className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-600 dark:bg-slate-800/30">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-600 dark:text-slate-300">{t('test.question')} {idx + 1}</span>
                    <button type="button" onClick={() => removeQuestion(idx)} className="rounded p-1 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  <input
                    value={q.text}
                    onChange={(e) => updateQuestion(idx, 'text', e.target.value)}
                    placeholder={t('test.questionText')}
                    className="mb-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                  />
                  <div className="flex flex-wrap gap-3">
                    {sections.length > 0 && (
                      <select
                        value={q.section_index ?? ''}
                        onChange={(e) => updateQuestion(idx, 'section_index', e.target.value === '' ? null : Number(e.target.value))}
                        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      >
                        <option value="">{t('test.noSection') || 'Aucune section'}</option>
                        {sections.map((sec, si) => (
                          <option key={si} value={si}>{sec.title || `Section ${si + 1}`}</option>
                        ))}
                      </select>
                    )}
                    <select
                      value={q.question_type}
                      onChange={(e) => updateQuestion(idx, 'question_type', e.target.value)}
                      className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                    >
                      {QUESTION_TYPES.map((opt) => (
                        <option key={opt.value} value={opt.value}>{t(opt.labelKey)}</option>
                      ))}
                    </select>
                    <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                      {t('test.points')}
                      <input
                        type="number"
                        min="0"
                        value={q.points}
                        onChange={(e) => updateQuestion(idx, 'points', parseInt(e.target.value, 10) || 0)}
                        className="w-16 rounded border border-slate-300 px-2 py-1 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </label>
                  </div>
                  {(q.question_type === 'single_choice' || q.question_type === 'multiple_choice') && (
                    <div className="mt-3 space-y-2">
                      <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{t('test.choices')}</p>
                      {(q.options || []).length === 0 && (
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {t('test.addOption')}
                        </p>
                      )}
                      {(q.options || []).map((opt, oi) => (
                        <div key={opt.id} className="flex flex-wrap items-center gap-2">
                          <input
                            value={opt.label}
                            onChange={(e) => updateQuestionOption(idx, oi, 'label', e.target.value)}
                            placeholder={`${t('test.optionLabel')} ${oi + 1}`}
                            className="min-w-[180px] flex-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                          />
                          <label className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
                            <input
                              type="checkbox"
                              checked={!!opt.correct}
                              onChange={(e) => updateQuestionOption(idx, oi, 'correct', e.target.checked)}
                              className="rounded border-slate-300 text-teal-600 dark:border-slate-600 dark:bg-slate-700"
                            />
                            {t('test.correctAnswer')}
                          </label>
                          {(q.options?.length ?? 0) > 2 && (
                            <button
                              type="button"
                              onClick={() => removeQuestionOption(idx, oi)}
                              className="rounded p-1 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                              title={t('test.removeOption')}
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={() => addQuestionOption(idx)}
                        className="inline-flex items-center gap-1 rounded-lg border border-dashed border-slate-400 px-3 py-1.5 text-sm text-slate-600 hover:border-teal-500 hover:text-teal-600 dark:border-slate-500 dark:text-slate-300 dark:hover:border-teal-400 dark:hover:text-teal-400"
                      >
                        <Plus className="h-4 w-4" />
                        {t('test.addOption')}
                      </button>
                    </div>
                  )}
                  {q.question_type === 'code' && (
                    <div className="mt-3 space-y-2">
                      <div className="flex gap-2">
                        <input
                          value={q.code_language ?? ''}
                          onChange={(e) => updateQuestion(idx, 'code_language', e.target.value)}
                          placeholder="Langage (ex: python, javascript)"
                          className="w-48 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                        />
                      </div>
                      <textarea
                        value={q.starter_code ?? ''}
                        onChange={(e) => updateQuestion(idx, 'starter_code', e.target.value)}
                        placeholder="Code de départ facultatif pour la question de programmation"
                        rows={4}
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-mono dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                      />
                    </div>
                  )}
                  {q.question_type === 'file_upload' && (
                    <div className="mt-3 rounded-lg border border-dashed border-slate-300 bg-white p-3 dark:border-slate-600 dark:bg-slate-700/50">
                      <label className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                        <Upload className="h-4 w-4" />
                        {t('test.attachmentQuestion')}
                      </label>
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.pbix,image/*"
                        onChange={(e) => {
                          const file = e.target.files?.[0] ?? null
                          updateQuestion(idx, 'attachmentFile', file)
                          if (file) updateQuestion(idx, 'attachmentUrl', null)
                        }}
                        className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-teal-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-teal-700 hover:file:bg-teal-100 dark:text-slate-300 dark:file:bg-teal-900/30 dark:file:text-teal-200 dark:hover:file:bg-teal-900/50"
                      />
                      {(q.attachmentUrl || q.attachmentFile) && (
                        <p className="mt-2 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                          <FileText className="h-3.5 w-3.5" />
                          {q.attachmentFile
                            ? q.attachmentFile.name
                            : q.attachmentUrl
                              ? (typeof q.attachmentUrl === 'string' && q.attachmentUrl.split('/').pop()) || t('test.attachmentUploaded')
                              : null}
                        </p>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex gap-3">
          <button type="submit" disabled={mutating} className="rounded-lg bg-teal-600 px-6 py-2.5 font-medium text-white hover:bg-teal-700 disabled:opacity-50">
            {mutating ? t('common.loading') : t('common.save')}
          </button>
          <button type="button" onClick={() => navigate('/tests')} className="rounded-lg border border-slate-300 px-6 py-2.5 font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700">
            {t('common.cancel')}
          </button>
        </div>
      </form>
    </div>
  )
}
