import { useEffect, useState } from 'react'
import { api, CatalogResponse } from '../api'

export function useCatalog(enabled: boolean): {
  catalog: CatalogResponse | null
  error: string | null
} {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api.catalog().then(
      (c) => { if (!cancelled) setCatalog(c) },
      (e) => { if (!cancelled) setError(String(e?.message ?? e)) },
    )
    return () => { cancelled = true }
  }, [enabled])

  return { catalog, error }
}
