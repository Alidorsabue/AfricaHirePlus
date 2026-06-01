import type { LucideIcon } from 'lucide-react'
import {
  LayoutDashboard,
  Briefcase,
  Kanban,
  FileText,
  Users,
  BarChart3,
  Pencil,
  ListOrdered,
  Mail,
  Settings,
  Shield,
} from 'lucide-react'

export type NavBadgeKey = 'dashboard' | 'jobs' | 'applications' | 'tests' | 'emails'

export interface RecruiterNavItem {
  to: string
  icon: LucideIcon
  labelKey: string
  badgeKey?: NavBadgeKey
  /** Correspondance exacte (ex. tableau de bord `/`). */
  end?: boolean
  /** Autres chemins qui activent cet item (ex. paramètres + entreprise). */
  alsoActiveOn?: string[]
}

export interface RecruiterNavSection {
  sectionKey: string
  items: RecruiterNavItem[]
}

export const recruiterNavSections: RecruiterNavSection[] = [
  {
    sectionKey: 'sectionRecruitment',
    items: [
      { to: '/', icon: LayoutDashboard, labelKey: 'dashboard', badgeKey: 'dashboard', end: true },
      { to: '/jobs', icon: Briefcase, labelKey: 'jobs', badgeKey: 'jobs' },
      { to: '/pipeline', icon: Kanban, labelKey: 'pipeline' },
      { to: '/applications', icon: FileText, labelKey: 'applications', badgeKey: 'applications' },
      { to: '/candidates', icon: Users, labelKey: 'candidates' },
    ],
  },
  {
    sectionKey: 'sectionEvaluation',
    items: [
      { to: '/scoring', icon: BarChart3, labelKey: 'scoringAts' },
      { to: '/tests', icon: Pencil, labelKey: 'tests', badgeKey: 'tests' },
      { to: '/shortlist', icon: ListOrdered, labelKey: 'shortlist' },
    ],
  },
  {
    sectionKey: 'sectionCommunication',
    items: [{ to: '/emails', icon: Mail, labelKey: 'emails', badgeKey: 'emails' }],
  },
  {
    sectionKey: 'sectionAdministration',
    items: [
      {
        to: '/settings',
        icon: Settings,
        labelKey: 'settings',
        alsoActiveOn: ['/company'],
      },
      { to: '/rgpd-audit', icon: Shield, labelKey: 'rgpdAudit' },
    ],
  },
]
