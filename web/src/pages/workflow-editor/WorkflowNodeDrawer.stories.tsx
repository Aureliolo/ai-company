import type { Meta, StoryObj } from '@storybook/react'
import { WorkflowNodeDrawer } from './WorkflowNodeDrawer'

const noop = () => {}

const meta: Meta = {
  title: 'Workflow Editor/Node Drawer',
  component: WorkflowNodeDrawer,
  parameters: { layout: 'padded' },
}

export default meta

export const TaskNode: StoryObj = {
  render: () => (
    <WorkflowNodeDrawer
      open
      onClose={noop}
      nodeId="task-1"
      nodeType="task"
      nodeLabel="Design API"
      config={{ title: 'Design API', priority: 'high', task_type: 'design' }}
      onConfigChange={noop}
    />
  ),
}

export const ConditionalNode: StoryObj = {
  render: () => (
    <WorkflowNodeDrawer
      open
      onClose={noop}
      nodeId="cond-1"
      nodeType="conditional"
      nodeLabel="Approved?"
      config={{ condition_expression: 'status == approved' }}
      onConfigChange={noop}
    />
  ),
}

export const Closed: StoryObj = {
  render: () => (
    <WorkflowNodeDrawer
      open={false}
      onClose={noop}
      nodeId={null}
      nodeType={null}
      nodeLabel="Node"
      config={{}}
      onConfigChange={noop}
    />
  ),
}
