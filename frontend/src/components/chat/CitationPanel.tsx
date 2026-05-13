import { useState } from 'react'
import { ChevronDown, BookOpen } from 'lucide-react'
import type { Citation } from '@/types'
import { cn } from '@/lib/utils'

interface CitationPanelProps {
  citations: Citation[]
}

export function CitationPanel({ citations }: CitationPanelProps) {
  const [open, setOpen] = useState(false)

  if (citations.length === 0) return null

  return (
    <div className="mt-3 rounded-lg border border-bg-border bg-bg-base/60 overflow-hidden">
      <button
        onClick={() => setOpen((s) => !s)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs text-txt-muted hover:text-txt-secondary transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <BookOpen size={11} />
          <span>{citations.length} {citations.length === 1 ? 'citation' : 'citations'}</span>
        </span>
        <ChevronDown
          size={12}
          className={cn('transition-transform duration-200', open && 'rotate-180')}
        />
      </button>
      {open && (
        <div className="border-t border-bg-border divide-y divide-bg-border animate-fade-in">
          {citations.map((c, i) => (
            <div key={c.chunk_id} className="px-3 py-2.5">
              <div className="flex items-center gap-2 mb-1">
                <span className="inline-flex h-4 w-4 items-center justify-center rounded bg-accent/15 text-accent text-[10px] font-bold font-mono shrink-0">
                  {i + 1}
                </span>
                <span className="text-xs font-medium text-txt-secondary truncate">
                  {c.document_title}
                </span>
                <span className="ml-auto text-xs text-txt-muted shrink-0">p.{c.page_number}</span>
              </div>
              {c.quote && (
                <p className="text-xs text-txt-muted italic leading-relaxed line-clamp-2 pl-6">
                  "{c.quote}"
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
