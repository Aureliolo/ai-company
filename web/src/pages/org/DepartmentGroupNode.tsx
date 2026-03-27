import { memo } from 'react'
import { type NodeProps, type Node } from '@xyflow/react'
import { cn, getHealthColor } from '@/lib/utils'
import { DepartmentStatsBar } from './DepartmentStatsBar'
import type { DepartmentGroupData } from './build-org-tree'

export type DepartmentGroupType = Node<DepartmentGroupData, 'department'>

const HEALTH_BG_CLASSES: Record<string, string> = {
  success: 'bg-success/8 border-success/20',
  accent: 'bg-accent/8 border-accent/20',
  warning: 'bg-warning/8 border-warning/20',
  danger: 'bg-danger/8 border-danger/20',
}

function DepartmentGroupNodeComponent({ data }: NodeProps<DepartmentGroupType>) {
  const healthColor = data.healthPercent !== null ? getHealthColor(data.healthPercent) : null
  const bgClasses = (healthColor && HEALTH_BG_CLASSES[healthColor]) ?? 'bg-card/50 border-border'

  return (
    <div
      className={cn(
        'rounded-xl border p-3',
        'min-h-[120px] min-w-[200px]',
        bgClasses,
      )}
      data-testid="department-group-node"
      aria-label={`Department: ${data.displayName}${data.healthPercent !== null ? `, health ${data.healthPercent}%` : ''}`}
    >
      <div className="mb-2">
        <div className="flex items-center justify-between">
          <span className="font-sans text-xs font-semibold text-foreground">
            {data.displayName}
          </span>
          <span className="font-mono text-micro font-medium text-muted-foreground">
            {data.healthPercent !== null ? `${data.healthPercent}%` : '--'}
          </span>
        </div>
        <DepartmentStatsBar
          agentCount={data.agentCount}
          activeCount={data.activeCount}
          taskCount={data.taskCount ?? 0}
          costUsd={data.costUsd}
          className="mt-1.5"
        />
      </div>
    </div>
  )
}

export const DepartmentGroupNode = memo(DepartmentGroupNodeComponent)
