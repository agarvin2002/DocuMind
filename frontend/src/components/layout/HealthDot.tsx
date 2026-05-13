import { useQuery } from '@tanstack/react-query'
import { checkHealth } from '@/api/health'
import * as Tooltip from '@radix-ui/react-tooltip'
import { cn } from '@/lib/utils'

export function HealthDot() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 30_000,
    retry: 1,
  })

  const healthy = !isLoading && !isError && data?.status === 'healthy'
  const unhealthy = isError || data?.status === 'unhealthy'

  const color = isLoading
    ? 'bg-txt-muted'
    : healthy
      ? 'bg-status-ready'
      : 'bg-status-failed'

  const label = isLoading
    ? 'Checking backend…'
    : healthy
      ? `Backend healthy · v${data?.version ?? '?'}`
      : `Backend ${unhealthy ? 'unhealthy' : 'unreachable'}`

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <div className="relative inline-flex items-center cursor-default">
          <div className={cn('h-2 w-2 rounded-full', color)} />
          {healthy && (
            <div className={cn('absolute h-2 w-2 rounded-full animate-pulse-dot opacity-75', color)} />
          )}
        </div>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="right"
          className="z-50 rounded-lg border border-bg-border bg-bg-elevated px-3 py-1.5 text-xs text-txt-secondary shadow-elevated"
          sideOffset={8}
        >
          {label}
          <Tooltip.Arrow className="fill-bg-elevated" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}
