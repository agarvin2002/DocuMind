import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Zap, Inbox } from 'lucide-react'
import { AnalysisForm } from '@/components/analysis/AnalysisForm'
import { JobCard } from '@/components/analysis/JobCard'
import { Separator } from '@/components/ui/separator'

interface LocalJob {
  id: string
  question: string
}

function EmptyJobs() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-bg-border bg-bg-surface">
        <Inbox size={20} className="text-txt-muted" />
      </div>
      <p className="text-sm text-txt-secondary font-medium">No analyses yet</p>
      <p className="mt-1 text-xs text-txt-muted">Submit a question to run an agent analysis job.</p>
    </div>
  )
}

export function AnalysisPage() {
  const [searchParams] = useSearchParams()
  const initialDocId = searchParams.get('docId') ?? undefined
  const [jobs, setJobs] = useState<LocalJob[]>([])

  const handleJobCreated = (jobId: string, question: string) => {
    setJobs((s) => [{ id: jobId, question }, ...s])
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-baseline gap-3">
        <h1 className="font-display text-2xl font-bold text-txt-primary">Deep Analysis</h1>
        <p className="text-sm text-txt-muted">LangGraph agent pipeline · multi-hop, comparison, contradiction</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Form panel */}
        <div className="rounded-xl border border-bg-border bg-bg-surface p-5">
          <div className="flex items-center gap-2 mb-5">
            <Zap size={15} className="text-accent" />
            <h2 className="text-sm font-semibold text-txt-primary">New Analysis</h2>
          </div>
          <AnalysisForm onJobCreated={handleJobCreated} initialDocId={initialDocId} />
        </div>

        {/* Jobs panel */}
        <div className="rounded-xl border border-bg-border bg-bg-surface p-5">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-txt-primary">Job History</h2>
            {jobs.length > 0 && (
              <span className="text-xs text-txt-muted">{jobs.length} job{jobs.length !== 1 ? 's' : ''}</span>
            )}
          </div>
          {jobs.length === 0 ? (
            <EmptyJobs />
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => (
                <JobCard key={job.id} jobId={job.id} initialQuestion={job.question} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
