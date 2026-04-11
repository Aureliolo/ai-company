import type { Meta, StoryObj } from '@storybook/react'
import { ReactFlow, ReactFlowProvider, type Node } from '@xyflow/react'
import { SubworkflowNode } from './SubworkflowNode'

const nodeTypes = { subworkflow: SubworkflowNode }

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
  title: 'Workflow Editor/Subworkflow Node',
  parameters: { layout: 'centered' },
}

export default meta

export const Configured: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{
        id: '1',
        type: 'subworkflow',
        position: { x: 0, y: 0 },
        data: {
          label: 'Quarterly Close',
          config: { subworkflow_id: 'sub-quarterly-close', version: '2.1.0' },
        },
      }]}
    />
  ),
}

export const Unconfigured: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{
        id: '1',
        type: 'subworkflow',
        position: { x: 0, y: 0 },
        data: { label: 'Subworkflow', config: {} },
      }]}
    />
  ),
}

export const Selected: StoryObj = {
  render: () => (
    <Wrapper
      nodes={[{
        id: '1',
        type: 'subworkflow',
        position: { x: 0, y: 0 },
        selected: true,
        data: {
          label: 'Data Pipeline',
          config: { subworkflow_id: 'sub-data-pipeline', version: '1.0.0' },
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
        type: 'subworkflow',
        position: { x: 0, y: 0 },
        data: {
          label: 'Broken Ref',
          config: { subworkflow_id: 'sub-missing', version: '1.0.0' },
          hasError: true,
        },
      }]}
    />
  ),
}
