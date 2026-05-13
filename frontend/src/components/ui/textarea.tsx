import { forwardRef, type TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'w-full rounded-lg border border-bg-border bg-bg-elevated px-3 py-2.5 text-sm text-txt-primary',
        'placeholder:text-txt-muted',
        'focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        'resize-none transition-colors duration-150',
        className
      )}
      {...props}
    />
  )
)
Textarea.displayName = 'Textarea'
