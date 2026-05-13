import * as RadixDialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

export const Dialog = RadixDialog.Root
export const DialogTrigger = RadixDialog.Trigger

interface DialogContentProps {
  children: ReactNode
  className?: string
  title?: string
  description?: string
}

export function DialogContent({ children, className, title, description }: DialogContentProps) {
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm animate-fade-in" />
      <RadixDialog.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2',
          'w-full max-w-md rounded-xl border border-bg-border bg-bg-elevated p-6 shadow-elevated',
          'animate-slide-up',
          'focus:outline-none',
          className
        )}
      >
        {title && (
          <RadixDialog.Title className="text-base font-semibold text-txt-primary mb-1">
            {title}
          </RadixDialog.Title>
        )}
        {description && (
          <RadixDialog.Description className="text-sm text-txt-secondary mb-5">
            {description}
          </RadixDialog.Description>
        )}
        {children}
        <RadixDialog.Close
          className="absolute right-4 top-4 rounded-md p-1 text-txt-muted hover:text-txt-primary hover:bg-bg-border transition-colors"
          aria-label="Close"
        >
          <X size={16} />
        </RadixDialog.Close>
      </RadixDialog.Content>
    </RadixDialog.Portal>
  )
}
