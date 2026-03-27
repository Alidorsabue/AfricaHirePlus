/**
 * URL de base de l’API REST.
 * En dev sans VITE_API_URL : préfixe relatif `/api/v1` pour passer par le proxy Vite (évite CORS et les blocages cross-origin).
 */
export function getApiBaseUrl(): string {
  return (
    import.meta.env.VITE_API_URL ||
    (import.meta.env.DEV ? '/api/v1' : 'http://127.0.0.1:8000/api/v1')
  )
}

/** Origine des fichiers médias (avatars, logos entreprise) — cohérent avec getApiBaseUrl(). */
export function getMediaBaseUrl(): string {
  const api = getApiBaseUrl()
  if (api.startsWith('http')) {
    return api.replace(/\/api\/v1\/?$/, '')
  }
  return ''
}
