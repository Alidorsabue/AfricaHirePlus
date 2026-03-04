import type { ReactNode } from 'react'
import ProtectedRoute from './ProtectedRoute'
import Layout from './Layout'

export function ProtectedLayout({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  )
}
