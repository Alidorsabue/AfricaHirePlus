/**
 * Point d'entrée de l'application AfricaHirePlus.
 * Fournit le router, React Query, thème, auth et définit toutes les routes (publiques, recruteur, candidat).
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import { ToastProvider } from './contexts/ToastContext'
import { RecruiterRoute } from './components/RecruiterRoute'
import { CandidateRoute } from './components/CandidateRoute'
import Login from './pages/Login'
import RegisterCompany from './pages/RegisterCompany'
import RegisterCandidate from './pages/RegisterCandidate'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import JobDetail from './pages/JobDetail'
import JobForm from './pages/JobForm'
import PublicJob from './pages/PublicJob'
import PublicJobApply from './pages/PublicJobApply'
import Pipeline from './pages/Pipeline'
import Candidates from './pages/Candidates'
import CandidateProfile from './pages/CandidateProfile'
import Tests from './pages/Tests'
import TestForm from './pages/TestForm'
import TestResults from './pages/TestResults'
import TestResultDetail from './pages/TestResultDetail'
import TechnicalTest from './pages/TechnicalTest'
import EmailTemplates from './pages/EmailTemplates'
import CompanyProfile from './pages/CompanyProfile'
import ApplicationDetail from './pages/ApplicationDetail'
import MesCandidatures from './pages/MesCandidatures'
import TestAccess from './pages/TestAccess'
import OffresCandidat from './pages/OffresCandidat'
import MonProfil from './pages/MonProfil'
import './i18n'

// Client React Query : 1 retry, pas de refetch au focus
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

/** Déclaration des routes : login/register, offres publiques, espace candidat, espace recruteur. */
function AppRoutes() {
  const { user } = useAuth()
  return (
    <Routes>
      {/* Routes publiques : login, inscription entreprise/candidat */}
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/register" element={user ? <Navigate to="/" replace /> : <RegisterCompany />} />
      <Route path="/register/candidate" element={<RegisterCandidate />} />
      {/* Offres publiques (sans auth) : détail offre, formulaire de candidature */}
      <Route path="/offres/:slug" element={<PublicJob />} />
      <Route path="/offres/:slug/postuler" element={<PublicJobApply />} />
      {/* Espace candidat : mes candidatures, liste des offres, mon profil */}
      <Route path="/candidat" element={<CandidateRoute><MesCandidatures /></CandidateRoute>} />
      <Route path="/candidat/offres" element={<CandidateRoute><OffresCandidat /></CandidateRoute>} />
      <Route path="/candidat/profil" element={<CandidateRoute><MonProfil /></CandidateRoute>} />
      <Route path="/candidat/tests/access" element={<CandidateRoute><TestAccess /></CandidateRoute>} />
      <Route path="/candidat/tests/:testId" element={<CandidateRoute><TechnicalTest /></CandidateRoute>} />
      {/* Espace recruteur : dashboard, offres, pipeline, candidats, tests, emails */}
      <Route path="/" element={<RecruiterRoute><Dashboard /></RecruiterRoute>} />
      <Route path="/jobs" element={<RecruiterRoute><Jobs /></RecruiterRoute>} />
      <Route path="/jobs/new" element={<RecruiterRoute><JobForm /></RecruiterRoute>} />
      <Route path="/jobs/:id" element={<RecruiterRoute><JobDetail /></RecruiterRoute>} />
      <Route path="/jobs/:id/edit" element={<RecruiterRoute><JobForm /></RecruiterRoute>} />
      <Route path="/pipeline" element={<RecruiterRoute><Pipeline /></RecruiterRoute>} />
      <Route path="/applications/:id" element={<RecruiterRoute><ApplicationDetail /></RecruiterRoute>} />
      <Route path="/candidates" element={<RecruiterRoute><Candidates /></RecruiterRoute>} />
      <Route path="/candidates/:id" element={<RecruiterRoute><CandidateProfile /></RecruiterRoute>} />
      <Route path="/tests" element={<RecruiterRoute><Tests /></RecruiterRoute>} />
      <Route path="/tests/new" element={<RecruiterRoute><TestForm /></RecruiterRoute>} />
      <Route path="/tests/results" element={<RecruiterRoute><TestResults /></RecruiterRoute>} />
      <Route path="/tests/results/:id" element={<RecruiterRoute><TestResultDetail /></RecruiterRoute>} />
      <Route path="/tests/:id/edit" element={<RecruiterRoute><TestForm /></RecruiterRoute>} />
      <Route path="/tests/:testId" element={<RecruiterRoute><TechnicalTest /></RecruiterRoute>} />
      <Route path="/emails" element={<RecruiterRoute><EmailTemplates /></RecruiterRoute>} />
      <Route path="/company" element={<RecruiterRoute><CompanyProfile /></RecruiterRoute>} />
      {/* Fallback : redirection vers la home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

/** App : providers (Query, Router, Theme, Auth) + AppRoutes. */
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <ToastProvider>
              <AppRoutes />
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
