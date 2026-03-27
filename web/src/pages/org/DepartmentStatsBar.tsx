import { StatPill } from '@/components/ui/stat-pill'
import { formatCurrency } from '@/utils/format'
import { cn } from '@/lib/utils'

interface DepartmentStatsBarProps {
  agentCount: number
  activeCount: number
  taskCount: number
  costUsd: number | null
  currency?: string
  className?: string
}

export function DepartmentStatsBar({
  agentCount,
  activeCount,
  taskCount,
  costUsd,
  currency,
  className,
}: DepartmentStatsBarProps) {
  return (
    <div className={cn('flex flex-wrap gap-1.5', className)} data-testid="dept-stats-bar">
      <StatPill label="Agents" value={agentCount} />
      <StatPill label="Active" value={activeCount} />
      <StatPill label="Tasks" value={taskCount} />
      {costUsd !== null && <StatPill label="Cost" value={formatCurrency(costUsd, currency)} />}
    </div>
  )
}
