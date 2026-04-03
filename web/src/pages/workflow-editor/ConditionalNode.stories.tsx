import type { Meta, StoryObj } from '@storybook/react'
import { ReactFlow, ReactFlowProvider, type Node } from '@xyflow/react'
import { ConditionalNode } from './ConditionalNode'

const nodeTypes = { conditional: ConditionalNode }

function Wrapper({ nodes }: { nodes: Node[] }) {
  return (
    <ReactFlowProvider>
      <div className="h-64 w-80">
        <ReactFlow
          nodes={nodes}
          edges={[]}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
        />
      </div>
    </ReactFlowProvider>
  )
}

const meta: Meta = {
  title: 'Workflow Editor/Conditional Node',
  component: ConditionalNode,
  parameters: { layout: 'centered' },
}

export default meta

export const Default: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{
        id: '1',
        type: 'conditional',
        position: { x: 0, y: 0 },
        data: {
          label: 'Approved?',
          config: { condition_expression: 'approved?' },
        },
      }]}
    />
  ),
}
