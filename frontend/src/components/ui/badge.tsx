import { type HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

type Variant = 'default' | 'accent' | 'success' | 'warning' | 'error' | 'processing'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant
}

const variants: Record<Variant, string> = {
  default: 'bg-bg-elevated text-txt-secondary border-bg-border',
  accent: 'bg-accent/10 text-accent border-accent/20',
  success: 'bg-status-ready/10 text-status-ready border-status-ready/20',
  warning: 'bg-status-pending/10 text-status-pending border-status-pending/20',
  error: 'bg-status-failed/10 text-status-failed border-status-failed/20',
  processing: 'bg-status-processing/10 text-status-processing border-status-processing/20',
}

export function Badge({ className, variant = 'default', children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border',
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
}
