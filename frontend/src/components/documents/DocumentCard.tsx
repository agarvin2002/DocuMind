import { useNavigate } from 'react-router-dom'
import { MessageSquare, Zap, FileText, Hash, Calendar } from 'lucide-react'
import { StatusBadge } from './StatusBadge'
import { Button } from '@/components/ui/button'
import { formatFileSize, formatDate, truncate } from '@/lib/utils'
import type { Document } from '@/types'
import { cn } from '@/lib/utils'

interface DocumentCardProps {
  document: Document
}

export function DocumentCard({ document: doc }: DocumentCardProps) {
  const navigate = useNavigate()
  const isReady = doc.status === 'ready'

  return (
    <div
      className={cn(
        'group relative flex flex-col rounded-xl border border-bg-border bg-bg-surface p-4',
        'transition-all duration-200 hover:border-bg-border/80',
        isReady && 'card-glow cursor-default'
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/8 border border-accent/15">
          <FileText size={15} className="text-accent/70" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-txt-primary truncate leading-tight">
            {truncate(doc.title, 42)}
          </h3>
          <p className="text-xs text-txt-muted mt-0.5 truncate">{doc.original_filename}</p>
        </div>
        <StatusBadge status={doc.status} className="shrink-0 ml-auto" />
      </div>

      {/* Error */}
      {doc.error_message && (
        <p className="mb-3 rounded-lg border border-status-failed/20 bg-status-failed/5 px-3 py-2 text-xs text-status-failed leading-relaxed">
          {doc.error_message}
        </p>
      )}

      {/* Meta */}
      <div className="flex items-center gap-3 text-xs text-txt-muted mb-4 flex-wrap">
        <span className="flex items-center gap-1">
          <FileText size={11} />
          {formatFileSize(doc.file_size)}
        </span>
        {doc.chunk_count !== null && (
          <span className="flex items-center gap-1">
            <Hash size={11} />
            {doc.chunk_count} chunks
          </span>
        )}
        <span className="flex items-center gap-1 ml-auto">
          <Calendar size={11} />
          {formatDate(doc.created_at)}
        </span>
      </div>

      {/* Actions */}
      <div className="flex gap-2 mt-auto">
        <Button
          variant="secondary"
          size="sm"
          className="flex-1 text-xs"
          disabled={!isReady}
          onClick={() => navigate(`/chat/${doc.id}`)}
        >
          <MessageSquare size={12} />
          Ask
        </Button>
        <Button
          variant="secondary"
          size="sm"
          className="flex-1 text-xs"
          disabled={!isReady}
          onClick={() => navigate(`/analysis?docId=${doc.id}`)}
        >
          <Zap size={12} />
          Analyze
        </Button>
      </div>
    </div>
  )
}

export function DocumentCardSkeleton() {
  return (
    <div className="rounded-xl border border-bg-border bg-bg-surface p-4 space-y-3">
      <div className="flex items-start gap-3">
        <div className="h-9 w-9 rounded-lg shimmer-bg" />
        <div className="flex-1 space-y-1.5">
          <div className="h-4 w-3/4 rounded shimmer-bg" />
          <div className="h-3 w-1/2 rounded shimmer-bg" />
        </div>
        <div className="h-5 w-16 rounded-md shimmer-bg" />
      </div>
      <div className="flex gap-3">
        <div className="h-3 w-12 rounded shimmer-bg" />
        <div className="h-3 w-16 rounded shimmer-bg" />
      </div>
      <div className="flex gap-2">
        <div className="h-7 flex-1 rounded-lg shimmer-bg" />
        <div className="h-7 flex-1 rounded-lg shimmer-bg" />
      </div>
    </div>
  )
}
