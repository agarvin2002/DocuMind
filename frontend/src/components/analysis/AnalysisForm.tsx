import { useState, useEffect } from 'react'
import { Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { WorkflowSelector } from './WorkflowSelector'
import { useDocumentStore } from '@/stores/documentStore'
import { createAnalysisJob } from '@/api/analysis'
import { toast } from '@/stores/toastStore'
import type { WorkflowType } from '@/types'

const MAX_CHARS = 2000

interface AnalysisFormProps {
  onJobCreated: (jobId: string, question: string) => void
  initialDocId?: string
}

export function AnalysisForm({ onJobCreated, initialDocId }: AnalysisFormProps) {
  const documents = useDocumentStore((s) => s.documents)
  const readyDocs = documents.filter((d) => d.status === 'ready')

  const [question, setQuestion] = useState('')
  const [selectedDocs, setSelectedDocs] = useState<string[]>(initialDocId ? [initialDocId] : [])
  const [workflow, setWorkflow] = useState<WorkflowType | 'auto'>('auto')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (initialDocId && !selectedDocs.includes(initialDocId)) {
      setSelectedDocs((s) => [...s, initialDocId])
    }
  }, [initialDocId])

  const toggleDoc = (id: string) => {
    setSelectedDocs((s) =>
      s.includes(id) ? s.filter((d) => d !== id) : [...s, id]
    )
  }

  const handleSubmit = async () => {
    if (!question.trim() || selectedDocs.length === 0) return
    setSubmitting(true)
    try {
      const job = await createAnalysisJob({
        question: question.trim(),
        document_ids: selectedDocs,
        workflow_type: workflow === 'auto' ? 'multi_hop' : workflow,
      })
      onJobCreated(job.id, question.trim())
      toast('Analysis job created', 'success')
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Failed to create analysis job', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Question */}
      <div className="space-y-2">
        <Label htmlFor="question">Question</Label>
        <Textarea
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value.slice(0, MAX_CHARS))}
          placeholder="What are the key risks, mitigations, and projected timeline described in this document?"
          rows={4}
        />
        <p className="text-right text-xs text-txt-muted">
          {question.length} / {MAX_CHARS}
        </p>
      </div>

      {/* Documents */}
      <div className="space-y-2">
        <Label>Documents</Label>
        {readyDocs.length === 0 ? (
          <p className="text-xs text-txt-muted py-2">
            No ready documents. Upload and process a PDF first.
          </p>
        ) : (
          <div className="space-y-1.5 max-h-40 overflow-y-auto">
            {readyDocs.map((doc) => (
              <label
                key={doc.id}
                className="flex items-center gap-3 rounded-lg border border-bg-border px-3 py-2.5 cursor-pointer hover:bg-bg-elevated transition-colors"
              >
                <Checkbox
                  checked={selectedDocs.includes(doc.id)}
                  onCheckedChange={() => toggleDoc(doc.id)}
                />
                <span className="text-sm text-txt-secondary truncate">{doc.title}</span>
                <span className="ml-auto text-xs text-txt-muted shrink-0">
                  {doc.chunk_count} chunks
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Workflow */}
      <div className="space-y-2">
        <Label>Workflow type</Label>
        <WorkflowSelector value={workflow} onChange={setWorkflow} />
      </div>

      <Button
        className="w-full"
        onClick={handleSubmit}
        loading={submitting}
        disabled={!question.trim() || selectedDocs.length === 0}
      >
        <Zap size={14} />
        Run Analysis
      </Button>
    </div>
  )
}
