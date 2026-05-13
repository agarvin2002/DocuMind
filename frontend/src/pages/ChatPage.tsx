import { useParams, useNavigate } from 'react-router-dom'
import { MessageSquare, ChevronDown } from 'lucide-react'
import { ChatInterface } from '@/components/chat/ChatInterface'
import { useDocumentStore } from '@/stores/documentStore'

function DocumentSelector({
  currentId,
  onSelect,
}: {
  currentId: string | undefined
  onSelect: (id: string) => void
}) {
  const documents = useDocumentStore((s) => s.documents)
  const readyDocs = documents.filter((d) => d.status === 'ready')
  const current = readyDocs.find((d) => d.id === currentId)

  if (readyDocs.length === 0) return null

  return (
    <div className="relative">
      <select
        value={currentId ?? ''}
        onChange={(e) => onSelect(e.target.value)}
        className="appearance-none rounded-lg border border-bg-border bg-bg-elevated pl-3 pr-8 py-2 text-sm text-txt-primary focus:outline-none focus:ring-1 focus:ring-accent cursor-pointer"
      >
        <option value="" disabled>Select a document…</option>
        {readyDocs.map((d) => (
          <option key={d.id} value={d.id}>{d.title}</option>
        ))}
      </select>
      <ChevronDown size={13} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-txt-muted" />
    </div>
  )
}

function EmptyState() {
  const documents = useDocumentStore((s) => s.documents)
  const readyDocs = documents.filter((d) => d.status === 'ready')
  const navigate = useNavigate()

  return (
    <div className="flex flex-col items-center justify-center h-full text-center py-24">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-bg-border bg-bg-surface">
        <MessageSquare size={24} className="text-txt-muted" />
      </div>
      {readyDocs.length === 0 ? (
        <>
          <h3 className="text-sm font-semibold text-txt-secondary">No documents ready</h3>
          <p className="mt-1.5 text-xs text-txt-muted max-w-xs">
            Upload and process a PDF on the{' '}
            <button
              className="text-accent hover:underline"
              onClick={() => navigate('/')}
            >
              Documents page
            </button>{' '}
            before chatting.
          </p>
        </>
      ) : (
        <>
          <h3 className="text-sm font-semibold text-txt-secondary">Select a document to begin</h3>
          <p className="mt-1.5 text-xs text-txt-muted">
            Use the dropdown above to choose a document.
          </p>
        </>
      )}
    </div>
  )
}

export function ChatPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const navigate = useNavigate()
  const documents = useDocumentStore((s) => s.documents)
  const currentDoc = documents.find((d) => d.id === documentId && d.status === 'ready')

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b border-bg-border bg-bg-surface px-5 py-3">
        <MessageSquare size={15} className="text-txt-muted" />
        <span className="text-sm font-medium text-txt-secondary">Chat with:</span>
        <DocumentSelector
          currentId={documentId}
          onSelect={(id) => navigate(`/chat/${id}`)}
        />
        {currentDoc && (
          <span className="ml-auto text-xs text-txt-muted">
            {currentDoc.chunk_count} chunks indexed
          </span>
        )}
      </div>

      {/* Chat or empty */}
      <div className="flex-1 overflow-hidden">
        {currentDoc ? (
          <ChatInterface document={currentDoc} />
        ) : (
          <EmptyState />
        )}
      </div>
    </div>
  )
}
