import { useQuery } from '@tanstack/react-query'
import { applicationsApi } from '../api/applications'
import { jobsApi } from '../api/jobs'
import { testsApi } from '../api/tests'
import { emailsApi } from '../api/emails'
import { unwrapList } from '../api/utils'

/** Compteurs affichés dans la barre latérale recruteur (badges). */
export function useRecruiterNavBadges() {
  const { data: applications = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: async () => unwrapList((await applicationsApi.list()).data),
  })
  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => unwrapList((await jobsApi.list()).data),
  })
  const { data: tests = [] } = useQuery({
    queryKey: ['tests'],
    queryFn: async () => unwrapList((await testsApi.list()).data),
  })
  const { data: templates = [] } = useQuery({
    queryKey: ['email-templates'],
    queryFn: async () => unwrapList((await emailsApi.listTemplates()).data),
  })

  const newApplications = applications.filter((a) => a.status === 'applied').length
  const publishedJobs = jobs.filter((j) => j.status === 'published').length
  const testsNeedingSetup = tests.filter((t) => !(t.questions?.length ?? 0)).length
  const inactiveTemplates = templates.filter((t) => t.is_active === false).length

  return {
    dashboard: newApplications,
    jobs: publishedJobs,
    applications: applications.length,
    tests: testsNeedingSetup,
    emails: inactiveTemplates,
  }
}
