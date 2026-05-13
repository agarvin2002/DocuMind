import type { HealthResponse } from '@/types'

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch('/api/v1/health/')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
