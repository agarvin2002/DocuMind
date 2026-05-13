import { User, Bot } from 'lucide-react'
import { StreamingText } from './StreamingText'
import { CitationPanel } from './CitationPanel'
import { CacheBadge } from './CacheBadge'
import type { ChatMessage } from '@/types'
import { formatDate } from '@/lib/utils'

interface MessageBubbleProps {
  message: ChatMessage
  isStreaming?: boolean
  streamingText?: string
  streamingCitations?: ChatMessage['citations']
}

export function MessageBubble({ message, isStreaming, streamingText, streamingCitations }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const displayText = isStreaming && streamingText !== undefined ? streamingText : message.content
  const displayCitations = isStreaming ? (streamingCitations ?? []) : (message.citations ?? [])

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="flex items-end gap-2 max-w-[75%]">
          <div className="rounded-2xl rounded-br-sm bg-accent/15 border border-accent/20 px-4 py-2.5">
            <p className="text-sm text-txt-primary leading-relaxed">{message.content}</p>
          </div>
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-bg-elevated border border-bg-border">
            <User size={13} className="text-txt-secondary" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3 max-w-[85%]">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/10 border border-accent/20 mt-0.5">
        <Bot size={13} className="text-accent" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-medium text-txt-muted">DocuMind</span>
          {message.isCached && !isStreaming && <CacheBadge />}
          <span className="ml-auto text-xs text-txt-disabled">{formatDate(message.timestamp)}</span>
        </div>
        <StreamingText text={displayText} isStreaming={isStreaming} />
        {!isStreaming && displayCitations.length > 0 && (
          <CitationPanel citations={displayCitations} />
        )}
      </div>
    </div>
  )
}
