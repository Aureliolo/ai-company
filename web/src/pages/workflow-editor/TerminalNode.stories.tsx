import type { Meta, StoryObj } from '@storybook/react'
import { ReactFlow, ReactFlowProvider, type Node } from '@xyflow/react'
import { StartNode } from './StartNode'
import { EndNode } from './EndNode'

const nodeTypes = { start: StartNode, end: EndNode }

function Wrapper({ nodes }: { nodes: Node[] }) {
  return (
    <ReactFlowProvider>
      <div className="h-40 w-52">
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
  title: 'Workflow Editor/Terminal Nodes',
  parameters: { layout: 'centered' },
}

export default meta

export const Start: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{ id: '1', type: 'start', position: { x: 0, y: 0 }, data: { label: 'Start' } }]}
    />
  ),
}

export const End: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{ id: '1', type: 'end', position: { x: 0, y: 0 }, data: { label: 'End' } }]}
    />
  ),
}
