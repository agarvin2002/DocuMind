import * as RadixAccordion from '@radix-ui/react-accordion'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

export const Accordion = RadixAccordion.Root

interface AccordionItemProps {
  value: string
  trigger: ReactNode
  children: ReactNode
  className?: string
}

export function AccordionItem({ value, trigger, children, className }: AccordionItemProps) {
  return (
    <RadixAccordion.Item value={value} className={cn('border-b border-bg-border last:border-0', className)}>
      <RadixAccordion.Trigger className="group flex w-full items-center justify-between py-3 text-left text-sm font-medium text-txt-secondary hover:text-txt-primary transition-colors [&[data-state=open]]:text-txt-primary">
        {trigger}
        <ChevronDown
          size={14}
          className="shrink-0 text-txt-muted transition-transform duration-200 group-data-[state=open]:rotate-180"
        />
      </RadixAccordion.Trigger>
      <RadixAccordion.Content className="overflow-hidden text-sm text-txt-secondary data-[state=open]:animate-fade-in data-[state=closed]:animate-none pb-3">
        {children}
      </RadixAccordion.Content>
    </RadixAccordion.Item>
  )
}
