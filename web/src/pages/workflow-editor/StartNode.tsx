import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import { Play } from 'lucide-react'

export interface StartNodeData extends Record<string, unknown> {
  label: string
}

export type StartNodeType = Node<StartNodeData, 'start'>

function StartNodeComponent({ data }: NodeProps<StartNodeType>) {
  return (
    <div
      className="flex size-10 items-center justify-center rounded-full border-2 border-accent bg-accent/10"
      data-testid="start-node"
      aria-label={`Start: ${data.label}`}
    >
      <Play className="size-4 text-accent" aria-hidden="true" />
      <Handle type="source" position={Position.Bottom} className="bg-accent! size-2!" />
    </div>
  )
}

export const StartNode = memo(StartNodeComponent)
