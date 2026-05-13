import { useState, useCallback, type DragEvent, type ChangeEvent } from 'react'
import { Upload, FileText, AlertCircle } from 'lucide-react'
import { uploadDocument } from '@/api/documents'
import { useDocumentStore } from '@/stores/documentStore'
import { toast } from '@/stores/toastStore'
import { cn } from '@/lib/utils'

const MAX_SIZE_MB = 50

export function UploadDropzone() {
  const addDocument = useDocumentStore((s) => s.addDocument)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFile = useCallback(
    async (file: File) => {
      setError(null)

      if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
        setError('Only PDF files are supported.')
        return
      }
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        setError(`File exceeds ${MAX_SIZE_MB} MB limit.`)
        return
      }

      setUploading(true)
      try {
        const title = file.name.replace(/\.pdf$/i, '')
        const doc = await uploadDocument(file, title)
        addDocument(doc)
        toast(`"${doc.title}" uploaded — processing…`, 'success')
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Upload failed'
        setError(msg)
        toast(msg, 'error')
      } finally {
        setUploading(false)
      }
    },
    [addDocument]
  )

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(true)
  }

  const onDragLeave = () => setDragging(false)

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  return (
    <label
      htmlFor="file-upload"
      className={cn(
        'relative flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition-all duration-200',
        dragging
          ? 'border-accent bg-accent/5 scale-[1.01]'
          : uploading
            ? 'border-accent/40 bg-accent/3 cursor-wait'
            : 'border-bg-border hover:border-accent/40 hover:bg-accent/3'
      )}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
    >
      <input
        id="file-upload"
        type="file"
        accept=".pdf,application/pdf"
        className="sr-only"
        onChange={onInputChange}
        disabled={uploading}
      />

      <div
        className={cn(
          'mb-3 flex h-12 w-12 items-center justify-center rounded-xl border transition-all duration-200',
          dragging
            ? 'border-accent bg-accent/15 text-accent'
            : 'border-bg-border bg-bg-elevated text-txt-muted'
        )}
      >
        {uploading ? (
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-r-transparent" />
        ) : (
          <Upload size={20} />
        )}
      </div>

      <p className="text-sm font-medium text-txt-secondary">
        {uploading ? 'Uploading…' : 'Drop a PDF here, or click to browse'}
      </p>
      <p className="mt-1 text-xs text-txt-muted">PDF only · max {MAX_SIZE_MB} MB</p>

      {error && (
        <div className="mt-3 flex items-center gap-1.5 text-xs text-status-failed">
          <AlertCircle size={12} />
          {error}
        </div>
      )}
    </label>
  )
}
