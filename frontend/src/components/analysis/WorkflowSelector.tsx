import * as Tooltip from '@radix-ui/react-tooltip'
import { cn } from '@/lib/utils'
import type { WorkflowType } from '@/types'

interface WorkflowOption {
  value: WorkflowType | 'auto'
  label: string
  description: string
  badge?: string
}

const options: WorkflowOption[] = [
  {
    value: 'auto',
    label: 'Auto-detect',
    description: 'The AI classifier determines the best workflow for your question.',
    badge: 'Recommended',
  },
  {
    value: 'multi_hop',
    label: 'Multi-hop',
    description: 'Breaks complex questions into sub-questions, retrieves answers independently, then synthesizes.',
  },
  {
    value: 'comparison',
    label: 'Comparison',
    description: 'Retrieves content from multiple documents and generates a structured comparison.',
  },
  {
    value: 'contradiction',
    label: 'Contradiction',
    description: 'Finds conflicts and inconsistencies within or between documents.',
  },
]

interface WorkflowSelectorProps {
  value: WorkflowType | 'auto'
  onChange: (value: WorkflowType | 'auto') => void
}

export function WorkflowSelector({ value, onChange }: WorkflowSelectorProps) {
  return (
    <div className="space-y-1.5">
      {options.map((opt) => (
        <Tooltip.Root key={opt.value}>
          <Tooltip.Trigger asChild>
            <button
              type="button"
              onClick={() => onChange(opt.value)}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-all duration-150',
                value === opt.value
                  ? 'border-accent/30 bg-accent/8 text-txt-primary'
                  : 'border-bg-border bg-bg-surface text-txt-secondary hover:border-bg-border/80 hover:text-txt-primary hover:bg-bg-elevated'
              )}
            >
              <div
                className={cn(
                  'h-3.5 w-3.5 shrink-0 rounded-full border-2 transition-colors',
                  value === opt.value ? 'border-accent bg-accent' : 'border-txt-muted'
                )}
              />
              <span className="text-sm font-medium">{opt.label}</span>
              {opt.badge && (
                <span className="ml-auto text-xs text-accent bg-accent/10 border border-accent/15 px-1.5 py-0.5 rounded">
                  {opt.badge}
                </span>
              )}
            </button>
          </Tooltip.Trigger>
          <Tooltip.Portal>
            <Tooltip.Content
              side="right"
              className="z-50 rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-xs text-txt-secondary shadow-elevated max-w-56"
              sideOffset={8}
            >
              {opt.description}
              <Tooltip.Arrow className="fill-bg-elevated" />
            </Tooltip.Content>
          </Tooltip.Portal>
        </Tooltip.Root>
      ))}
    </div>
  )
}
