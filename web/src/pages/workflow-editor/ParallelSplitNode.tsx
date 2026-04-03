import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import { SplitSquareVertical } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface ParallelSplitNodeData extends Record<string, unknown> {
  label: string
  config: Record<string, unknown>
  selected?: boolean
  hasError?: boolean
}

export type ParallelSplitNodeType = Node<ParallelSplitNodeData, 'parallel_split'>

function ParallelSplitNodeComponent({ data, selected }: NodeProps<ParallelSplitNodeType>) {
  return (
    <div
      className={cn(
        'flex h-8 min-w-32 items-center justify-center gap-1.5 rounded-md border border-accent/40 bg-accent/5 px-4',
        selected && 'ring-2 ring-accent',
        data.hasError && 'ring-2 ring-danger',
      )}
      data-testid="parallel-split-node"
      aria-label={`Parallel Split: ${data.label}`}
    >
      <Handle type="target" position={Position.Top} className="bg-border-bright! size-1.5!" />

      <SplitSquareVertical className="size-3.5 text-accent" aria-hidden="true" />
      <span className="font-sans text-micro font-medium text-foreground">Split</span>

      {/* Multiple source handles along the bottom */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="branch-0"
        className="bg-accent! size-1.5!"
        style={{ left: '33%' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="branch-1"
        className="bg-accent! size-1.5!"
        style={{ left: '66%' }}
      />
    </div>
  )
}

export const ParallelSplitNode = memo(ParallelSplitNodeComponent)
