import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Users } from 'lucide-react'
import type { TeamGroupData } from './build-org-tree'

export function TeamGroupNode({ data }: NodeProps) {
  const { teamName, memberCount } = data as TeamGroupData

  return (
    <div className="h-full w-full rounded-md border border-dashed border-border bg-bg-card/50 p-2">
      <Handle type="target" position={Position.Top} className="!bg-border" />
      <div className="flex items-center gap-1.5 pb-1">
        <Users className="size-3 text-text-muted" aria-hidden="true" />
        <span className="text-xs font-medium text-text-secondary truncate">
          {teamName}
        </span>
        <span className="ml-auto text-xs font-mono text-text-muted">
          {memberCount}
        </span>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-border" />
    </div>
  )
}
