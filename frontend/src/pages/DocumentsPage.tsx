import { UploadDropzone } from '@/components/documents/UploadDropzone'
import { DocumentGrid } from '@/components/documents/DocumentGrid'
import { useDocumentStore } from '@/stores/documentStore'

export function DocumentsPage() {
  const documents = useDocumentStore((s) => s.documents)

  const total = documents.length
  const ready = documents.filter((d) => d.status === 'ready').length
  const processing = documents.filter(
    (d) => d.status === 'pending' || d.status === 'processing'
  ).length

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-baseline gap-4">
        <h1 className="font-display text-2xl font-bold text-txt-primary">Documents</h1>
        {total > 0 && (
          <p className="text-sm text-txt-muted">
            {total} total · {ready} ready
            {processing > 0 && (
              <span className="text-status-processing"> · {processing} processing</span>
            )}
          </p>
        )}
      </div>

      {/* Upload */}
      <UploadDropzone />

      {/* Grid */}
      <DocumentGrid documents={documents} />
    </div>
  )
}
