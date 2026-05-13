import { useState } from 'react'
import { Search, SlidersHorizontal } from 'lucide-react'
import { SearchForm } from '@/components/search/SearchForm'
import { ChunkResult } from '@/components/search/ChunkResult'
import { searchChunks } from '@/api/query'
import { toast } from '@/stores/toastStore'
import type { SearchResponse } from '@/types'

function EmptyResults() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-bg-border bg-bg-surface">
        <Search size={20} className="text-txt-muted" />
      </div>
      <p className="text-sm text-txt-secondary font-medium">No search run yet</p>
      <p className="mt-1 text-xs text-txt-muted max-w-xs">
        Run a semantic search to inspect raw retrieval quality. Useful for tuning queries before using Chat.
      </p>
    </div>
  )
}

export function SearchPage() {
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<SearchResponse | null>(null)

  const handleSearch = async (query: string, documentId: string, k: number) => {
    setLoading(true)
    setResults(null)
    try {
      const data = await searchChunks({ query, document_id: documentId, k })
      setResults(data)
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Search failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-baseline gap-3">
        <h1 className="font-display text-2xl font-bold text-txt-primary">Search Explorer</h1>
        <span className="inline-flex items-center gap-1 text-xs text-txt-muted border border-bg-border rounded-md px-2 py-0.5">
          <SlidersHorizontal size={10} />
          Retrieval debugger
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        {/* Form */}
        <div className="rounded-xl border border-bg-border bg-bg-surface p-5 lg:sticky lg:top-6 self-start">
          <SearchForm onSearch={handleSearch} loading={loading} />
        </div>

        {/* Results */}
        <div className="space-y-3">
          {results && (
            <div className="flex items-center justify-between mb-1">
              <p className="text-sm text-txt-secondary">
                <span className="font-semibold text-txt-primary">{results.result_count}</span>{' '}
                results for{' '}
                <span className="italic text-txt-muted">"{results.query}"</span>
              </p>
              <p className="text-xs text-txt-muted">ranked by RRF fusion score</p>
            </div>
          )}

          {loading && (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-32 rounded-xl shimmer-bg" />
              ))}
            </div>
          )}

          {!loading && results && results.results.map((r, i) => (
            <ChunkResult key={r.chunk_id} result={r} rank={i + 1} />
          ))}

          {!loading && !results && <EmptyResults />}

          {!loading && results && results.results.length === 0 && (
            <div className="flex flex-col items-center py-12 text-center">
              <p className="text-sm text-txt-secondary">No chunks found</p>
              <p className="mt-1 text-xs text-txt-muted">
                Try rephrasing the query or increasing k.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
