import type { Meta, StoryObj } from '@storybook/react'
import { ReactFlow, ReactFlowProvider, type Node } from '@xyflow/react'
import { ParallelSplitNode } from './ParallelSplitNode'
import { ParallelJoinNode } from './ParallelJoinNode'

const nodeTypes = { parallel_split: ParallelSplitNode, parallel_join: ParallelJoinNode }

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
  title: 'Workflow Editor/Parallel Nodes',
  parameters: { layout: 'centered' },
}

export default meta

export const Split: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{
        id: '1',
        type: 'parallel_split',
        position: { x: 0, y: 0 },
        data: { label: 'Split', config: {} },
      }]}
    />
  ),
}

export const Join: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{
        id: '1',
        type: 'parallel_join',
        position: { x: 0, y: 0 },
        data: { label: 'Join', config: { join_strategy: 'all' } },
      }]}
    />
  ),
}
