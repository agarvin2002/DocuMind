import { useApiKeyStore } from '@/stores/apiKeyStore'
import { apiFetch } from './client'
import type { SearchResponse, Citation } from '@/types'

export interface AskParams {
  query: string
  document_id: string
  k?: number
  model?: string
}

interface StreamCallbacks {
  onToken: (token: string) => void
  onCitations: (citations: Citation[]) => void
  onDone: () => void
  onError: (error: string) => void
}

export async function searchChunks(params: {
  query: string
  document_id: string
  k?: number
}): Promise<SearchResponse> {
  const res = await apiFetch('/api/v1/query/search/', {
    method: 'POST',
    body: JSON.stringify(params),
  })
  return res.json()
}

export async function streamAsk(
  params: AskParams,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const apiKey = useApiKeyStore.getState().apiKey

  let response: Response
  try {
    response = await fetch('/api/v1/query/ask/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(params),
      signal,
    })
  } catch (err) {
    if ((err as Error).name === 'AbortError') return
    callbacks.onError('Network error — is the backend running?')
    return
  }

  if (!response.ok) {
    try {
      const body = await response.json()
      callbacks.onError(body.detail ?? `HTTP ${response.status}`)
    } catch {
      callbacks.onError(`HTTP ${response.status}`)
    }
    return
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() ?? ''

      for (const block of blocks) {
        if (!block.trim()) continue
        const lines = block.split('\n')
        const eventLine = lines.find((l) => l.startsWith('event:'))
        const dataLine = lines.find((l) => l.startsWith('data:'))
        const data = dataLine ? dataLine.slice(6) : ''

        if (eventLine?.includes('citations')) {
          try {
            callbacks.onCitations(JSON.parse(data))
          } catch {
            // ignore parse errors
          }
        } else if (eventLine?.includes('done')) {
          callbacks.onDone()
          reader.cancel()
          return
        } else if (eventLine?.includes('error')) {
          callbacks.onError(data)
          return
        } else if (data && !eventLine) {
          callbacks.onToken(data)
        }
      }
    }
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      callbacks.onError('Stream interrupted')
    }
  }
}
