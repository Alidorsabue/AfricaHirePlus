/**
 * Garde de route pour l'espace recruteur (admin / recruteur) : exige un utilisateur connecté.
 * Les candidats sont redirigés vers /candidat. Enveloppe le contenu dans Layout (sidebar + header).
 */
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import ProtectedRoute from './ProtectedRoute'
import Layout from './Layout'

export function RecruiterRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="text-center">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-teal-500 border-t-transparent dark:border-teal-400" />
          <p className="mt-4 text-slate-600 dark:text-slate-400">Chargement...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <ProtectedRoute>{null}</ProtectedRoute>
  }

  if (user.role === 'candidate') {
    return <Navigate to="/candidat" replace />
  }

  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  )
}
