import { useState, type FormEvent } from 'react'
import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { useDocumentStore } from '@/stores/documentStore'

interface SearchFormProps {
  onSearch: (query: string, documentId: string, k: number) => void
  loading?: boolean
}

export function SearchForm({ onSearch, loading }: SearchFormProps) {
  const documents = useDocumentStore((s) => s.documents)
  const readyDocs = documents.filter((d) => d.status === 'ready')

  const [query, setQuery] = useState('')
  const [docId, setDocId] = useState(readyDocs[0]?.id ?? '')
  const [k, setK] = useState(10)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!query.trim() || !docId) return
    onSearch(query.trim(), docId, k)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="search-doc">Document</Label>
        <select
          id="search-doc"
          value={docId}
          onChange={(e) => setDocId(e.target.value)}
          className="w-full rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-sm text-txt-primary focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
        >
          {readyDocs.length === 0 && (
            <option value="">No ready documents</option>
          )}
          {readyDocs.map((d) => (
            <option key={d.id} value={d.id}>{d.title}</option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="search-query">Query</Label>
        <Input
          id="search-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="what are the main risks described?"
        />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label>Results (k)</Label>
          <span className="font-mono text-sm text-accent">{k}</span>
        </div>
        <Slider value={k} onValueChange={setK} min={1} max={20} />
        <div className="flex justify-between text-xs text-txt-muted">
          <span>1</span>
          <span>20</span>
        </div>
      </div>

      <Button
        type="submit"
        className="w-full"
        loading={loading}
        disabled={!query.trim() || !docId}
      >
        <Search size={14} />
        Search
      </Button>
    </form>
  )
}
