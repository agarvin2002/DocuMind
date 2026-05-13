import { Upload } from 'lucide-react'
import { DocumentCard, DocumentCardSkeleton } from './DocumentCard'
import type { Document } from '@/types'

interface DocumentGridProps {
  documents: Document[]
  loading?: boolean
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-bg-border bg-bg-surface">
        <Upload size={24} className="text-txt-muted" />
      </div>
      <h3 className="text-sm font-semibold text-txt-secondary">No documents yet</h3>
      <p className="mt-1 text-xs text-txt-muted max-w-xs">
        Upload a PDF above to get started. Documents are indexed with hybrid semantic + keyword search.
      </p>
    </div>
  )
}

export function DocumentGrid({ documents, loading }: DocumentGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <DocumentCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (documents.length === 0) {
    return <EmptyState />
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {documents.map((doc) => (
        <DocumentCard key={doc.id} document={doc} />
      ))}
    </div>
  )
}
