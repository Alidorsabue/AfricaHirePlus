import type { AxiosError } from 'axios'

/** 404 attendus (nouveau candidat sans profil / sans candidature sur l'offre). */
function isExpectedNotFound(err: AxiosError): boolean {
  if (err.response?.status !== 404) return false
  const url = `${err.config?.url ?? ''}`
  return (
    url.includes('/candidates/me') ||
    url.includes('/applications/my-application') ||
    url.includes('/applications/last-cv-info')
  )
}

/** Logs détaillés des erreurs API (console navigateur — F12). */
export function logApiFailure(context: string, err: AxiosError): void {
  if (isExpectedNotFound(err)) {
    return
  }

  const cfg = err.config
  const base = cfg?.baseURL ?? ''
  const path = cfg?.url ?? ''
  const attempted = `${base}${path}`.replace(/([^:]\/)\/+/g, '$1')

  const payload = {
    context,
    attemptedUrl: attempted,
    method: cfg?.method?.toUpperCase(),
    message: err.message,
    code: err.code,
    status: err.response?.status,
    responseData: err.response?.data,
    networkOrCors: !err.response && (err.message === 'Network Error' || err.code === 'ERR_NETWORK'),
  }

  console.error('[AfricaHire+ API]', payload)
  if (payload.networkOrCors) {
    console.error(
      '[AfricaHire+ API] Indice : sans réponse HTTP (réseau / CORS / mauvaise URL). ' +
        'Vérifiez VITE_API_URL au moment du build Railway et CORS_ALLOWED_ORIGINS côté Django.'
    )
  }
}
