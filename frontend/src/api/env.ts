/**
 * Normalise VITE_API_URL : Django monte l’API sous `/api/v1/`.
 * Beaucoup de déploiements Railway ne mettent que `.../api` → les appels partent vers `/api/auth/...` (inexistant).
 */
function normalizeViteApiUrl(url: string): string {
  const u = url.trim().replace(/\/+$/, '')
  if (/\/api$/i.test(u)) {
    return `${u}/v1`
  }
  return u
}

/**
 * URL de base de l’API REST.
 * - Dev sans VITE_API_URL : `/api/v1` (proxy Vite).
 * - Prod sans VITE_API_URL : **jamais** `127.0.0.1` (le navigateur appellerait la machine du visiteur).
 *   → `/api/v1` sur la même origine (reverse proxy) ou configurez VITE_API_URL au **build** (Railway).
 */
export function getApiBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_URL
  if (typeof fromEnv === 'string' && fromEnv.trim()) {
    return normalizeViteApiUrl(fromEnv)
  }
  if (import.meta.env.DEV) {
    return '/api/v1'
  }
  if (typeof window !== 'undefined') {
    const h = window.location.hostname
    if (h === 'localhost' || h === '127.0.0.1') {
      return 'http://127.0.0.1:8000/api/v1'
    }
  }
  return '/api/v1'
}

let diagnosticsLogged = false

/** Une fois au chargement : URL résolue + avertissement si build sans VITE_API_URL. */
export function logApiDiagnostics(): void {
  if (diagnosticsLogged) return
  diagnosticsLogged = true

  const base = getApiBaseUrl()
  const raw = import.meta.env.VITE_API_URL
  const defined = typeof raw === 'string' && raw.trim().length > 0

  console.info('[AfricaHire+ API] Configuration', {
    resolvedBaseUrl: base,
    mode: import.meta.env.MODE,
    viteApiUrlInBuild: defined ? raw : '(non défini au build — les variables Runtime Railway ne suffisent pas pour Vite)',
  })

  if (import.meta.env.PROD && !defined) {
    console.warn(
      '[AfricaHire+ API] VITE_API_URL absent du bundle. ' +
        'Dans Railway : ajoutez VITE_API_URL aux variables du service frontend, cochez « Available at Build Time » (ou équivalent), puis redéployez. ' +
        'Sinon les appels partent en relatif `/api/v1` sur ce domaine uniquement.'
    )
  }
}
/** Origine des fichiers médias (avatars, logos entreprise) — cohérent avec getApiBaseUrl(). */
export function getMediaBaseUrl(): string {
  const api = getApiBaseUrl()
  if (api.startsWith('http')) {
    return api.replace(/\/api\/v1\/?$/, '')
  }
  return ''
}
