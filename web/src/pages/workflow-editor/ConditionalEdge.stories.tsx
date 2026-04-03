import type { Meta, StoryObj } from '@storybook/react'
import {
  ReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
  Position,
} from '@xyflow/react'
import { ConditionalEdge } from './ConditionalEdge'

const edgeTypes = { conditional: ConditionalEdge }

const nodes: Node[] = [
  {
    id: 'a',
    position: { x: 80, y: 0 },
    data: { label: 'Condition' },
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
  },
  {
    id: 'b',
    position: { x: 0, y: 120 },
    data: { label: 'True' },
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
  },
  {
    id: 'c',
    position: { x: 160, y: 120 },
    data: { label: 'False' },
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
  },
]

const edges: Edge[] = [
  {
    id: 'e-true',
    source: 'a',
    target: 'b',
    type: 'conditional',
    data: { branch: 'true' },
  },
  {
    id: 'e-false',
    source: 'a',
    target: 'c',
    type: 'conditional',
    data: { branch: 'false' },
  },
]

function Wrapper() {
  return (
    <ReactFlowProvider>
      <div className="h-64 w-80">
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
  title: 'Workflow Editor/Conditional Edge',
  component: ConditionalEdge,
  parameters: { layout: 'centered' },
}

export default meta

export const Default: StoryObj = {
  render: () => <Wrapper />,
}
