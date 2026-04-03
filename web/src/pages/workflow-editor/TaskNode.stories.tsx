import type { Meta, StoryObj } from '@storybook/react'
import { ReactFlow, ReactFlowProvider, type Node } from '@xyflow/react'
import { TaskNode } from './TaskNode'

const nodeTypes = { task: TaskNode }

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
  title: 'Workflow Editor/Task Node',
  parameters: { layout: 'centered' },
}

export default meta

export const Default: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{
        id: '1',
        type: 'task',
        position: { x: 0, y: 0 },
        data: {
          label: 'Design API',
          config: { title: 'Design API', task_type: 'design', priority: 'high' },
        },
      }]}
    />
  ),
}

export const Selected: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{
        id: '1',
        type: 'task',
        position: { x: 0, y: 0 },
        selected: true,
        data: {
          label: 'Implementation',
          config: { title: 'Implementation', priority: 'medium' },
        },
      }]}
    />
  ),
}

export const WithError: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{
        id: '1',
        type: 'task',
        position: { x: 0, y: 0 },
        data: {
          label: 'Missing Title',
          config: {},
          hasError: true,
        },
      }]}
    />
  ),
}
