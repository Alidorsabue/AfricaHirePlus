/**
 * Django REST renvoie des listes paginées { results, count, next, previous }.
 * Cette fonction retourne toujours un tableau.
 */
export function unwrapList<T>(data: T[] | { results?: T[] } | undefined): T[] {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object' && 'results' in data && Array.isArray((data as { results: T[] }).results)) {
    return (data as { results: T[] }).results
  }
  return []
}
