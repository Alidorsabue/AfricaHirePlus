import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { logApiDiagnostics } from './api/env'
import './index.css'

logApiDiagnostics()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
