import * as RadixLabel from '@radix-ui/react-label'
import { cn } from '@/lib/utils'
import type { ComponentPropsWithoutRef } from 'react'

type LabelProps = ComponentPropsWithoutRef<typeof RadixLabel.Root>

export function Label({ className, ...props }: LabelProps) {
  return (
    <RadixLabel.Root
      className={cn('text-xs font-medium text-txt-secondary uppercase tracking-wider', className)}
      {...props}
    />
  )
}
