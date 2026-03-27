import type { Meta, StoryObj } from '@storybook/react'
import { TaskDependencyGraph } from './TaskDependencyGraph'
import type { Task } from '@/api/types'

function makeTask(id: string, title: string, overrides: Partial<Task> = {}): Task {
  return {
    id,
    title,
    description: 'Description',
    type: 'development',
    status: 'in_progress',
    priority: 'medium',
    project: 'test-project',
    created_by: 'agent-cto',
    assigned_to: 'agent-eng',
    reviewers: [],
    dependencies: [],
    artifacts_expected: [],
    acceptance_criteria: [],
    estimated_complexity: 'medium',
    budget_limit: 10,
    deadline: null,
    max_retries: 3,
    parent_task_id: null,
    delegation_chain: [],
    task_structure: null,
    coordination_topology: 'auto',
    version: 1,
    created_at: '2026-03-20T10:00:00Z',
    updated_at: '2026-03-25T14:00:00Z',
    ...overrides,
  }
}

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
    onSelectTask: () => {},
  },
}

export const NoDependencies: Story = {
  args: {
    tasks: [
      makeTask('t1', 'Standalone task'),
      makeTask('t2', 'Another task'),
    ],
    onSelectTask: () => {},
  },
}

export const Empty: Story = {
  args: {
    tasks: [],
    onSelectTask: () => {},
  },
}
