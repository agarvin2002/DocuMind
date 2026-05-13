import { Zap } from 'lucide-react'
import * as Tooltip from '@radix-ui/react-tooltip'

export function CacheBadge() {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <span className="inline-flex items-center gap-1 rounded-md border border-accent/20 bg-accent/8 px-1.5 py-0.5 text-xs font-medium text-accent cursor-default">
          <Zap size={10} className="fill-accent" />
          Cached
        </span>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="top"
          className="z-50 rounded-lg border border-bg-border bg-bg-elevated px-3 py-1.5 text-xs text-txt-secondary shadow-elevated max-w-48 text-center"
          sideOffset={6}
        >
          Served from semantic cache — semantically equivalent question answered previously
          <Tooltip.Arrow className="fill-bg-elevated" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}
