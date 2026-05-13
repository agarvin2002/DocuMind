import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { Send, Square, Trash2 } from 'lucide-react'
import { MessageBubble } from './MessageBubble'
import { Button } from '@/components/ui/button'
import { useStreamingAsk } from '@/hooks/useStreamingAsk'
import { useChatStore } from '@/stores/chatStore'
import { toast } from '@/stores/toastStore'
import type { Document } from '@/types'

interface ChatInterfaceProps {
  document: Document
}

export function ChatInterface({ document: doc }: ChatInterfaceProps) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const { addMessage } = useChatStore()
  const messages = useChatStore((s) => s.conversations[doc.id] ?? [])
  const clearConversation = useChatStore((s) => s.clearConversation)

  const { isStreaming, answer, citations, error, isCached, ask, cancel } = useStreamingAsk()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, answer])

  useEffect(() => {
    if (error) {
      toast(error, 'error')
    }
  }, [error])

  const prevStreamingRef = useRef(false)
  useEffect(() => {
    if (prevStreamingRef.current && !isStreaming && answer) {
      addMessage(doc.id, {
        id: `a-${Date.now()}`,
        role: 'assistant' as const,
        content: answer,
        citations,
        isCached,
        timestamp: new Date().toISOString(),
      })
    }
    prevStreamingRef.current = isStreaming
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStreaming])

  const handleSend = async () => {
    const query = input.trim()
    if (!query || isStreaming) return

    const userMsg = {
      id: `u-${Date.now()}`,
      role: 'user' as const,
      content: query,
      timestamp: new Date().toISOString(),
    }
    addMessage(doc.id, userMsg)
    setInput('')

    await ask({ query, document_id: doc.id })
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.length === 0 && !isStreaming && (
          <div className="flex flex-col items-center justify-center h-full text-center py-16">
            <div className="mb-3 h-12 w-12 rounded-2xl border border-accent/20 bg-accent/8 flex items-center justify-center">
              <span className="text-xl">✦</span>
            </div>
            <p className="text-sm font-medium text-txt-secondary">
              Ask anything about <span className="text-txt-primary">{doc.title}</span>
            </p>
            <p className="mt-1 text-xs text-txt-muted">Answers are grounded in the document with citations</p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isStreaming && (
          <MessageBubble
            message={{
              id: 'streaming',
              role: 'assistant',
              content: answer,
              isCached,
              timestamp: new Date().toISOString(),
            }}
            isStreaming={isStreaming}
            streamingText={answer || ''}
            streamingCitations={citations}
          />
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-bg-border bg-bg-surface px-4 py-3">
        <div className="flex items-end gap-2">
          <div className="relative flex-1">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              placeholder="Ask anything about this document… (⌘↵ to send)"
              rows={1}
              className="w-full resize-none rounded-xl border border-bg-border bg-bg-elevated px-4 py-3 text-sm text-txt-primary placeholder:text-txt-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent disabled:opacity-40 transition-colors leading-relaxed max-h-40 overflow-y-auto"
              style={{ height: 'auto', minHeight: '48px' }}
              onInput={(e) => {
                const el = e.currentTarget
                el.style.height = 'auto'
                el.style.height = `${Math.min(el.scrollHeight, 160)}px`
              }}
            />
          </div>
          <div className="flex gap-1.5 pb-0.5">
            {messages.length > 0 && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => clearConversation(doc.id)}
                title="Clear conversation"
                className="h-10 w-10"
              >
                <Trash2 size={14} />
              </Button>
            )}
            {isStreaming ? (
              <Button
                variant="danger"
                size="icon"
                onClick={cancel}
                title="Stop streaming"
                className="h-10 w-10"
              >
                <Square size={14} className="fill-current" />
              </Button>
            ) : (
              <Button
                size="icon"
                onClick={handleSend}
                disabled={!input.trim()}
                title="Send (⌘↵)"
                className="h-10 w-10"
              >
                <Send size={14} />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
