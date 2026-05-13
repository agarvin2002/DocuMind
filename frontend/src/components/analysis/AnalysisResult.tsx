import { CheckCircle, AlertCircle, BookOpen, GitBranch } from 'lucide-react'
import { Accordion, AccordionItem } from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { StreamingText } from '@/components/chat/StreamingText'
import type { AnalysisJob } from '@/types'
import { formatDuration } from '@/lib/utils'

interface AnalysisResultProps {
  job: AnalysisJob
}

const workflowLabels: Record<string, string> = {
  simple: 'Simple',
  multi_hop: 'Multi-hop',
  comparison: 'Comparison',
  contradiction: 'Contradiction',
}

export function AnalysisResult({ job }: AnalysisResultProps) {
  const result = job.result_data
  if (!result) return null

  const isError = !!result.error
  const hasSubQuestions = result.sub_questions.length > 0

  const elapsed =
    job.started_at && job.completed_at
      ? Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000)
      : null

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-2 flex-wrap">
        {isError ? (
          <AlertCircle size={14} className="text-status-failed" />
        ) : (
          <CheckCircle size={14} className="text-status-ready" />
        )}
        <span className="text-sm font-medium text-txt-primary">
          {isError ? 'Analysis failed' : 'Analysis complete'}
        </span>
        <Badge variant="accent">
          {workflowLabels[result.workflow_type] ?? result.workflow_type}
        </Badge>
        {elapsed !== null && (
          <span className="text-xs text-txt-muted ml-auto">
            completed in {formatDuration(elapsed)}
          </span>
        )}
      </div>

      {/* Final Answer */}
      <div className="rounded-xl border border-bg-border bg-bg-surface p-4">
        <p className="text-xs font-medium text-txt-muted uppercase tracking-wider mb-3">Final Answer</p>
        <StreamingText text={result.final_answer} />
      </div>

      {/* Sub-questions accordion */}
      {hasSubQuestions && (
        <div className="rounded-xl border border-bg-border bg-bg-surface overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-bg-border">
            <GitBranch size={13} className="text-txt-muted" />
            <p className="text-xs font-medium text-txt-muted uppercase tracking-wider">
              Sub-questions ({result.sub_questions.length})
            </p>
          </div>
          <div className="px-4">
            <Accordion type="multiple">
              {result.sub_questions.map((q, i) => (
                <AccordionItem
                  key={i}
                  value={`sq-${i}`}
                  trigger={
                    <span className="flex items-center gap-2">
                      <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded bg-accent/15 text-accent text-[10px] font-bold font-mono">
                        {i + 1}
                      </span>
                      <span>{q}</span>
                    </span>
                  }
                >
                  <div className="pl-6 text-txt-secondary leading-relaxed">
                    {result.sub_answers[i] ?? '—'}
                  </div>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </div>
      )}

      {/* Citations */}
      {result.citations.length > 0 && (
        <div className="rounded-xl border border-bg-border bg-bg-surface p-4">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen size={13} className="text-txt-muted" />
            <p className="text-xs font-medium text-txt-muted uppercase tracking-wider">
              Sources ({result.citations.length})
            </p>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {result.citations.map((c, i) => (
              <div
                key={`${c.chunk_id}-${i}`}
                className="flex items-center gap-2.5 rounded-lg border border-bg-border bg-bg-elevated px-3 py-2"
              >
                <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded bg-accent/15 text-accent text-[10px] font-bold font-mono">
                  {i + 1}
                </span>
                <span className="text-xs text-txt-secondary truncate">{c.document_title}</span>
                <span className="ml-auto text-xs text-txt-muted shrink-0">p.{c.page_number}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
