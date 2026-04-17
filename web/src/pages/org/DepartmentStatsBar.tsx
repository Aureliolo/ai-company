import { StatPill } from '@/components/ui/stat-pill'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import { formatCurrency } from '@/utils/format'
import { cn } from '@/lib/utils'

interface DepartmentStatsBarProps {
  agentCount: number
  activeCount: number
  cost7d: number | null
  currency?: string
  className?: string
}

export function DepartmentStatsBar({
  agentCount,
  activeCount,
  cost7d,
  currency = DEFAULT_CURRENCY,
  className,
}: DepartmentStatsBarProps) {
  return (
    <div className={cn('flex flex-wrap gap-1.5', className)} data-testid="dept-stats-bar">
      <StatPill label="Agents" value={agentCount} />
      <StatPill label="Active" value={activeCount} />
      {cost7d !== null && Number.isFinite(cost7d) && (
        <StatPill label="Cost (7d)" value={formatCurrency(cost7d, currency)} />
      )}
    </div>
  )
}
