import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import { Avatar } from '@/components/ui/avatar'
import { StatusBadge } from '@/components/ui/status-badge'
import { cn, getStatusColor } from '@/lib/utils'
import type { AgentNodeData } from './build-org-tree'

export type AgentNodeType = Node<AgentNodeData, 'agent'>

const STATUS_RING_CLASSES: Record<string, string> = {
  success: 'ring-success/40',
  accent: 'ring-accent/20',
  warning: 'ring-warning/40',
  danger: 'ring-danger/40',
  'text-secondary': 'ring-border',
}

function AgentNodeComponent({ data }: NodeProps<AgentNodeType>) {
  const statusColor = getStatusColor(data.runtimeStatus)
  const isActive = data.runtimeStatus === 'active'
  const isOffline = data.runtimeStatus === 'offline'

  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-card px-3 py-2',
        'min-w-36 max-w-44',
        'ring-1',
        STATUS_RING_CLASSES[statusColor] ?? 'ring-border',
        isOffline && 'opacity-50',
      )}
      data-testid="agent-node"
      aria-label={`Agent: ${data.name}, ${data.role}, ${data.runtimeStatus}`}
    >
      <Handle type="target" position={Position.Top} className="bg-border-bright! size-1.5!" />

      <div className="flex items-center gap-2">
        <Avatar name={data.name} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="truncate font-sans text-xs font-semibold text-foreground">
              {data.name}
            </span>
            <StatusBadge
              status={data.runtimeStatus}
              pulse={isActive || data.runtimeStatus === 'error'}
            />
          </div>
          <span className="block truncate font-sans text-micro text-muted-foreground">
            {data.role}
          </span>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="bg-border-bright! size-1.5!" />
    </div>
  )
}

export const AgentNode = memo(AgentNodeComponent)
