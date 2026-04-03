import type { Meta, StoryObj } from '@storybook/react'
import {
  ReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
  Position,
} from '@xyflow/react'
import { SequentialEdge } from './SequentialEdge'

const edgeTypes = { sequential: SequentialEdge }

const nodes: Node[] = [
  {
    id: 'a',
    position: { x: 50, y: 0 },
    data: { label: 'Step 1' },
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
  },
  {
    id: 'b',
    position: { x: 50, y: 120 },
    data: { label: 'Step 2' },
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
  },
]

const edges: Edge[] = [
  {
    id: 'e-seq',
    source: 'a',
    target: 'b',
    type: 'sequential',
  },
]

function Wrapper() {
  return (
    <ReactFlowProvider>
      <div className="h-64 w-52">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          edgeTypes={edgeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
        />
      </div>
    </ReactFlowProvider>
  )
}

const meta: Meta = {
  title: 'Workflow Editor/Sequential Edge',
  component: SequentialEdge,
  parameters: { layout: 'centered' },
}

export default meta

export const Default: StoryObj = {
  render: () => <Wrapper />,
}
