import { useState, useEffect } from 'react'
import { ChevronDown, Loader2, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { useAnalysisPolling } from '@/hooks/useAnalysisPolling'
import { AnalysisResult } from './AnalysisResult'
import { Badge } from '@/components/ui/badge'
import { formatDuration, truncate } from '@/lib/utils'
import { cn } from '@/lib/utils'

interface JobCardProps {
  jobId: string
  initialQuestion: string
}

const statusConfig = {
  pending: { icon: Loader2, label: 'Pending', variant: 'default' as const, spin: true },
  running: { icon: Loader2, label: 'Running', variant: 'processing' as const, spin: true },
  complete: { icon: CheckCircle, label: 'Complete', variant: 'success' as const, spin: false },
  failed: { icon: AlertCircle, label: 'Failed', variant: 'error' as const, spin: false },
}

export function JobCard({ jobId, initialQuestion }: JobCardProps) {
  const { data: job } = useAnalysisPolling(jobId)
  const [expanded, setExpanded] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const startRef = useState(() => Date.now())[0]

  useEffect(() => {
    if (job?.status === 'complete' || job?.status === 'failed') return
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [job?.status, startRef])

  const status = job?.status ?? 'pending'
  const { icon: StatusIcon, label, variant, spin } = statusConfig[status]
  const isTerminal = status === 'complete' || status === 'failed'

  return (
    <div className={cn(
      'rounded-xl border bg-bg-surface overflow-hidden transition-all duration-200',
      status === 'complete' ? 'border-status-ready/15' :
      status === 'failed' ? 'border-status-failed/15' :
      'border-bg-border'
    )}>
      {/* Header */}
      <button
        onClick={() => isTerminal && setExpanded((s) => !s)}
        className={cn(
          'flex w-full items-center gap-3 px-4 py-3 text-left',
          isTerminal && 'hover:bg-bg-elevated/50 transition-colors cursor-pointer',
          !isTerminal && 'cursor-default'
        )}
      >
        <StatusIcon
          size={14}
          className={cn(
            variant === 'success' ? 'text-status-ready' :
            variant === 'error' ? 'text-status-failed' :
            variant === 'processing' ? 'text-status-processing' : 'text-txt-muted',
            spin && 'animate-spin'
          )}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-txt-primary truncate">
            {truncate(initialQuestion, 60)}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <Badge variant={variant} className="text-xs">{label}</Badge>
            {job?.result_data?.workflow_type && (
              <span className="text-xs text-txt-muted">{job.result_data.workflow_type}</span>
            )}
            {!isTerminal && (
              <span className="flex items-center gap-1 text-xs text-txt-muted">
                <Clock size={10} />
                {formatDuration(elapsed)}
              </span>
            )}
          </div>
        </div>
        {isTerminal && (
          <ChevronDown
            size={14}
            className={cn(
              'shrink-0 text-txt-muted transition-transform duration-200',
              expanded && 'rotate-180'
            )}
          />
        )}
      </button>

      {/* Expanded result */}
      {expanded && job && (
        <div className="border-t border-bg-border px-4 py-4 animate-fade-in">
          <AnalysisResult job={job} />
        </div>
      )}
    </div>
  )
}
