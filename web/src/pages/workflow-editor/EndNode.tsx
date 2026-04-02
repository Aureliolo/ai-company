import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import { Square } from 'lucide-react'

export interface EndNodeData extends Record<string, unknown> {
  label: string
}

export type EndNodeType = Node<EndNodeData, 'end'>

function EndNodeComponent({ data }: NodeProps<EndNodeType>) {
  return (
    <div
      className="flex size-10 items-center justify-center rounded-full border-2 border-muted-foreground bg-muted-foreground/10"
      data-testid="end-node"
      aria-label={`End: ${data.label}`}
    >
      <Square className="size-3.5 text-muted-foreground" aria-hidden="true" />
      <Handle type="target" position={Position.Top} className="bg-border-bright! size-2!" />
    </div>
  )
}

export const EndNode = memo(EndNodeComponent)
