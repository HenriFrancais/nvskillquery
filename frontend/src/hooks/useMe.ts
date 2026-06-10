import { useEffect, useState } from 'react'
import { api, MeResponse } from '../api'

export function useMe(): { me: MeResponse | null; error: string | null } {
  const [me, setMe] = useState<MeResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api.me().then(
      (m) => { if (!cancelled) setMe(m) },
      (e) => { if (!cancelled) setError(String(e?.message ?? e)) },
    )
    return () => { cancelled = true }
  }, [])

  return { me, error }
}
