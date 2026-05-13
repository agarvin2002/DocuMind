import { useState } from 'react'
import { ChevronDown, FileText } from 'lucide-react'
import type { SearchResult } from '@/types'
import { cn } from '@/lib/utils'

interface ChunkResultProps {
  result: SearchResult
  rank: number
}

export function ChunkResult({ result, rank }: ChunkResultProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="rounded-xl border border-bg-border bg-bg-surface overflow-hidden animate-slide-up">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-bg-border bg-bg-elevated/50">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-accent/10 text-accent text-xs font-bold font-mono shrink-0">
          {rank}
        </span>
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <FileText size={12} className="text-txt-muted shrink-0" />
          <span className="text-xs font-medium text-txt-secondary truncate">
            {result.document_title}
          </span>
        </div>
        <span className="text-xs text-txt-muted shrink-0 border border-bg-border bg-bg-elevated rounded px-2 py-0.5">
          p.{result.page_number}
        </span>
        <span className="font-mono text-xs text-accent shrink-0">
          {result.score.toFixed(4)}
        </span>
      </div>

      {/* Child text */}
      <div className="px-4 py-3">
        <p className="text-sm text-txt-primary leading-relaxed">{result.child_text}</p>
      </div>

      {/* Parent context toggle */}
      <button
        onClick={() => setExpanded((s) => !s)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs text-txt-muted hover:text-txt-secondary border-t border-bg-border hover:bg-bg-elevated/30 transition-colors"
      >
        <span>Show parent context (512 tokens)</span>
        <ChevronDown
          size={12}
          className={cn('transition-transform duration-200', expanded && 'rotate-180')}
        />
      </button>

      {expanded && (
        <div className="border-t border-bg-border px-4 py-3 bg-bg-elevated/20 animate-fade-in">
          <p className="text-xs text-txt-muted leading-relaxed font-mono whitespace-pre-wrap">
            {result.parent_text}
          </p>
        </div>
      )}
    </div>
  )
}
