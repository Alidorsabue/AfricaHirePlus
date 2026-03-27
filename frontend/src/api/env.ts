/**
 * Normalise VITE_API_URL : Django n’expose que `/api/v1/` (minuscules). `/api/V1/` → 404.
 * Utilise l’API URL pour le pathname (fiable quelle que soit la casse du segment).
 */
function normalizeViteApiUrl(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, '')
  if (!trimmed) return trimmed

  if (/^https?:\/\//i.test(trimmed)) {
    try {
      const u = new URL(trimmed)
      let p = u.pathname.replace(/\/api\/v1/gi, '/api/v1')
      if (/\/api$/i.test(p)) {
        p = `${p}/v1`
      }
      u.pathname = p
      const out = `${u.origin}${u.pathname}`.replace(/\/$/, '')
      return out
    } catch {
      /* fallthrough */
    }
  }

  let s = trimmed.replace(/\/api\/v1/gi, '/api/v1')
  if (/\/api$/i.test(s)) {
    s = `${s}/v1`
  }
  return s
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
    return api.replace(/\/api\/v1\/?$/i, '')
  }
  return ''
}

/**
 * URL affichable pour un média renvoyé par l’API (ex. avatar : `/media/...`).
 * Sans cela, le navigateur charge `/media/...` sur le domaine du frontend → 404 en prod (API sur autre host).
 */
export function resolveMediaUrl(path: string | null | undefined): string | null {
  if (!path?.trim()) return null
  const p = path.trim()
  if (p.startsWith('http://') || p.startsWith('https://')) return p
  const base = getMediaBaseUrl()
  return `${base}${p.startsWith('/') ? '' : '/'}${p}`
}
