import { cn } from '@/lib/utils'
import type { DocumentStatus } from '@/types'

interface StatusBadgeProps {
  status: DocumentStatus
  className?: string
}

const configs: Record<
  DocumentStatus,
  { label: string; dotClass: string; textClass: string; bgClass: string }
> = {
  pending: {
    label: 'Pending',
    dotClass: 'bg-status-pending',
    textClass: 'text-status-pending',
    bgClass: 'bg-status-pending/8 border-status-pending/20',
  },
  processing: {
    label: 'Processing',
    dotClass: 'bg-status-processing animate-pulse',
    textClass: 'text-status-processing',
    bgClass: 'bg-status-processing/8 border-status-processing/20',
  },
  ready: {
    label: 'Ready',
    dotClass: 'bg-status-ready',
    textClass: 'text-status-ready',
    bgClass: 'bg-status-ready/8 border-status-ready/20',
  },
  failed: {
    label: 'Failed',
    dotClass: 'bg-status-failed',
    textClass: 'text-status-failed',
    bgClass: 'bg-status-failed/8 border-status-failed/20',
  },
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const { label, dotClass, textClass, bgClass } = configs[status]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium',
        bgClass,
        textClass,
        className
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', dotClass)} />
      {label}
    </span>
  )
}
