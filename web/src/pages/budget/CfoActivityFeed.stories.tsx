import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router'
import { CfoActivityFeed } from './CfoActivityFeed'
import type { ActivityItem } from '@/api/types/analytics'

const mockEvents: ActivityItem[] = [
  {
    id: '1',
    timestamp: '2026-03-26T12:00:00.000Z',
    agent_name: 'cfo-agent',
    action_type: 'budget.record_added',
    description: 'Recorded API cost for auth module task',
    task_id: 'task-42',
    department: 'engineering',
  },
  {
    id: '2',
    timestamp: '2026-03-26T11:55:00.000Z',
    agent_name: 'cfo-agent',
    action_type: 'budget.alert',
    description: 'Budget warning threshold reached at 78%',
    task_id: null,
    department: null,
  },
  {
    id: '3',
    timestamp: '2026-03-26T11:50:00.000Z',
    agent_name: 'agent-eng-1',
    action_type: 'budget.record_added',
    description: 'Recorded inference cost for code review',
    task_id: 'task-38',
    department: 'engineering',
  },
  {
    id: '4',
    timestamp: '2026-03-26T11:45:00.000Z',
    agent_name: 'agent-designer',
    action_type: 'budget.record_added',
    description: 'Recorded cost for wireframe generation',
    task_id: 'task-35',
    department: 'design',
  },
  {
    id: '5',
    timestamp: '2026-03-26T11:40:00.000Z',
    agent_name: 'cfo-agent',
    action_type: 'budget.alert',
    description: 'Auto-downgrade triggered for low-priority tasks',
    task_id: null,
    department: null,
  },
]

const meta = {
  title: 'Budget/CfoActivityFeed',
  component: CfoActivityFeed,
  tags: ['autodocs'],
  parameters: { a11y: { test: 'error' } },
  decorators: [
    (Story) => (
      <MemoryRouter>
        <div className="max-w-2xl">
          <Story />
        </div>
      </MemoryRouter>
    ),
  ],
} satisfies Meta<typeof CfoActivityFeed>

export default meta
type Story = StoryObj<typeof meta>

export const WithEvents: Story = {
  args: {
    events: mockEvents,
  },
}

export const Empty: Story = {
  args: {
    events: [],
  },
}
