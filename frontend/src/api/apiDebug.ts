import type { AxiosError } from 'axios'

/** Logs détaillés des erreurs API (console navigateur — F12). */
export function logApiFailure(context: string, err: AxiosError): void {
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
