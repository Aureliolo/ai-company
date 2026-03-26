import { useCallback, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { useAnalyticsStore } from '@/stores/analytics'
import { usePolling } from '@/hooks/usePolling'
import { getHealth } from '@/api/endpoints/health'
import { HEALTH_POLL_INTERVAL } from '@/utils/constants'
import type { HealthStatus } from '@/api/types'

type SystemStatus = 'ok' | 'degraded' | 'down'

const STATUS_CONFIG: Record<SystemStatus, { color: string; label: string }> = {
  ok: { color: 'bg-success', label: 'all systems nominal' },
  degraded: { color: 'bg-warning', label: 'system degraded' },
  down: { color: 'bg-danger', label: 'system down' },
}

export function StatusBar() {
  const totalAgents = useAnalyticsStore((s) => s.overview?.total_agents ?? 0)
  const activeAgents = useAnalyticsStore((s) => s.overview?.active_agents_count ?? 0)
  const totalTasks = useAnalyticsStore((s) => s.overview?.total_tasks ?? 0)
  const totalCost = useAnalyticsStore((s) => s.overview?.total_cost_usd)

  const [healthStatus, setHealthStatus] = useState<SystemStatus>('ok')

  // Trigger overview fetch on mount if data isn't loaded yet
  useEffect(() => {
    const state = useAnalyticsStore.getState()
    if (!state.overview && !state.loading) {
      state.fetchOverview()
    }
  }, [])

  // Poll system health
  const pollHealth = useCallback(async () => {
    try {
      const health: HealthStatus = await getHealth()
      setHealthStatus(health.status)
    } catch {
      setHealthStatus('down')
    }
  }, [])

  const healthPolling = usePolling(pollHealth, HEALTH_POLL_INTERVAL)
  useEffect(() => {
    healthPolling.start()
    return () => healthPolling.stop()
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [])

  const statusCfg = STATUS_CONFIG[healthStatus]
  const costDisplay =
    totalCost !== undefined && totalCost !== null
      ? `$${totalCost.toFixed(2)}`
      : '$--'

  return (
    <div
      className={cn(
        'flex h-8 shrink-0 items-center gap-6',
        'border-b border-border bg-background px-6',
        'text-[11px] tracking-wide font-mono',
        'text-text-secondary select-none',
      )}
    >
      <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
        SynthOrg
      </span>

      <Divider />

      <StatusItem>
        <Dot color="bg-accent" />
        <span>{totalAgents} agents</span>
      </StatusItem>

      <StatusItem>
        <Dot color="bg-success" />
        <span>{activeAgents} active</span>
      </StatusItem>

      <StatusItem>
        <Dot color="bg-warning" />
        <span>{totalTasks} tasks</span>
      </StatusItem>

      <Divider />

      <StatusItem>
        <span className="text-muted-foreground">spend</span>
        <span className="ml-1.5 text-foreground">{costDisplay}</span>
        <span className="ml-1 text-muted-foreground">today</span>
      </StatusItem>

      <div className="flex-1" />

      <StatusItem>
        <Dot color={statusCfg.color} />
        <span className="text-muted-foreground">{statusCfg.label}</span>
      </StatusItem>
    </div>
  )
}

function Divider() {
  return <span className="h-3 w-px shrink-0 bg-border" />
}

function Dot({ color }: { color: string }) {
  return (
    <span
      className={cn('mr-1.5 inline-block size-[5px] shrink-0 rounded-full', color)}
      aria-hidden="true"
    />
  )
}

function StatusItem({ children }: { children: React.ReactNode }) {
  return (
    <span className="flex items-center whitespace-nowrap">{children}</span>
  )
}
