import { useState, useCallback, useRef } from 'react'
import { streamAsk, type AskParams } from '@/api/query'
import type { Citation } from '@/types'

interface StreamingState {
  isStreaming: boolean
  answer: string
  citations: Citation[]
  error: string | null
  isCached: boolean
}

const initial: StreamingState = {
  isStreaming: false,
  answer: '',
  citations: [],
  error: null,
  isCached: false,
}

export function useStreamingAsk() {
  const [state, setState] = useState<StreamingState>(initial)
  const abortRef = useRef<AbortController | null>(null)
  const startTimeRef = useRef(0)
  const firstTokenRef = useRef(true)

  const ask = useCallback(async (params: AskParams) => {
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    startTimeRef.current = Date.now()
    firstTokenRef.current = true

    setState({ isStreaming: true, answer: '', citations: [], error: null, isCached: false })

    await streamAsk(
      params,
      {
        onToken: (token) => {
          if (firstTokenRef.current) {
            const elapsed = Date.now() - startTimeRef.current
            firstTokenRef.current = false
            setState((prev) => ({
              ...prev,
              isCached: elapsed < 150,
              answer: prev.answer + token,
            }))
          } else {
            setState((prev) => ({ ...prev, answer: prev.answer + token }))
          }
        },
        onCitations: (citations) => setState((prev) => ({ ...prev, citations })),
        onDone: () => setState((prev) => ({ ...prev, isStreaming: false })),
        onError: (error) => setState((prev) => ({ ...prev, isStreaming: false, error })),
      },
      abortRef.current.signal
    )
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setState((prev) => ({ ...prev, isStreaming: false }))
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setState(initial)
  }, [])

  return { ...state, ask, cancel, reset }
}
