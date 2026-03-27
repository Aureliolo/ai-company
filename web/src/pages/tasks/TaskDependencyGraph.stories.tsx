import type { Meta, StoryObj } from '@storybook/react'
import { action } from 'storybook/actions'
import { TaskDependencyGraph } from './TaskDependencyGraph'
import { makeTask } from '@/__tests__/helpers/factories'

const meta = {
  title: 'Tasks/TaskDependencyGraph',
  component: TaskDependencyGraph,
  tags: ['autodocs'],
  parameters: { layout: 'padded' },
} satisfies Meta<typeof TaskDependencyGraph>

export default meta
type Story = StoryObj<typeof meta>

export const WithDependencies: Story = {
  args: {
    tasks: [
      makeTask('t1', 'Design system', { status: 'completed' }),
      makeTask('t2', 'API endpoints', { status: 'in_progress', dependencies: ['t1'] }),
      makeTask('t3', 'Frontend UI', { status: 'assigned', dependencies: ['t1', 't2'] }),
      makeTask('t4', 'Integration tests', { status: 'created', dependencies: ['t2', 't3'] }),
    ],
    onSelectTask: action('onSelectTask'),
  },
}

export const NoDependencies: Story = {
  args: {
    tasks: [
      makeTask('t1', 'Standalone task'),
      makeTask('t2', 'Another task'),
    ],
    onSelectTask: action('onSelectTask'),
  },
}

export const Empty: Story = {
  args: {
    tasks: [],
    onSelectTask: action('onSelectTask'),
  },
}
