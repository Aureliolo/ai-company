import { MetricCard } from '@/components/ui/metric-card'
import { formatLatency, formatErrorRate } from '@/utils/providers'
import type { ProviderHealthSummary } from '@/api/types'

interface ProviderHealthMetricsProps {
  health: ProviderHealthSummary
}

export function ProviderHealthMetrics({ health }: ProviderHealthMetricsProps) {
  const lastCheck = health.last_check_timestamp
    ? new Date(health.last_check_timestamp).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
    : '--'

  return (
    <div className="grid grid-cols-4 gap-grid-gap max-[1023px]:grid-cols-2">
      <MetricCard
        label="Calls (24h)"
        value={health.calls_last_24h.toLocaleString()}
      />
      <MetricCard
        label="Avg Response Time"
        value={formatLatency(health.avg_response_time_ms)}
      />
      <MetricCard
        label="Error Rate (24h)"
        value={formatErrorRate(health.error_rate_percent_24h)}
      />
      <MetricCard
        label="Last Check"
        value={lastCheck}
      />
    </div>
  )
}
