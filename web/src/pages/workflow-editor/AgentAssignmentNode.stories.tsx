import type { Meta, StoryObj } from '@storybook/react'
import { ReactFlow, ReactFlowProvider, type Node } from '@xyflow/react'
import { AgentAssignmentNode } from './AgentAssignmentNode'

const nodeTypes = { agent_assignment: AgentAssignmentNode }

function Wrapper({ nodes }: { nodes: Node[] }) {
  return (
    <ReactFlowProvider>
      <div className="h-52 w-80">
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
  title: 'Workflow Editor/Agent Assignment Node',
  parameters: { layout: 'centered' },
}

export default meta

export const Default: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{
        id: '1',
        type: 'agent_assignment',
        position: { x: 0, y: 0 },
        data: {
          label: 'Assign',
          config: { routing_strategy: 'role_based', role_filter: 'engineer' },
        },
      }]}
    />
  ),
}
