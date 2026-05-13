import { useApiKeyStore } from '@/stores/apiKeyStore'

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const apiKey = useApiKeyStore.getState().apiKey
  const headers = new Headers(options.headers)
  if (apiKey) headers.set('X-API-Key', apiKey)
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(path, { ...options, headers })

  if (!response.ok && response.status !== 200) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.clone().json()
      detail = body.detail ?? detail
    } catch {
      // ignore
    }
    throw new ApiError(detail, response.status)
  }

  return response
}
