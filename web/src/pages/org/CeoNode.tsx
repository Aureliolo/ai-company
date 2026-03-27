import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import { Avatar } from '@/components/ui/avatar'
import { StatusBadge } from '@/components/ui/status-badge'
import { cn } from '@/lib/utils'
import type { CeoNodeData } from './build-org-tree'

export type CeoNodeType = Node<CeoNodeData, 'ceo'>

function CeoNodeComponent({ data }: NodeProps<CeoNodeType>) {
  const isActive = data.runtimeStatus === 'active'

  return (
    <div
      className={cn(
        'rounded-lg border border-accent/30 bg-card px-4 py-3',
        'min-w-[180px] max-w-[220px]',
        'shadow-sm shadow-accent/15',
      )}
      data-testid="ceo-node"
      aria-label={`CEO: ${data.name}, ${data.companyName}`}
    >
      <Handle type="target" position={Position.Top} className="bg-accent! size-1.5!" />

      <div className="mb-1 text-center font-sans text-micro font-medium tracking-wide text-accent">
        {data.companyName}
      </div>

      <div className="flex items-center gap-2.5">
        <Avatar name={data.name} size="md" borderColor="border-accent/40" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="truncate font-sans text-sm font-semibold text-foreground">
              {data.name}
            </span>
            <StatusBadge
              status={data.runtimeStatus}
              pulse={isActive || data.runtimeStatus === 'error'}
            />
          </div>
          <span className="block truncate font-sans text-xs text-muted-foreground">
            {data.role}
          </span>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="bg-accent! size-1.5!" />
    </div>
  )
}

export const CeoNode = memo(CeoNodeComponent)
