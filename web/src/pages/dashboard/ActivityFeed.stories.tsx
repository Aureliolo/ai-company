import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router'
import { ActivityFeed } from './ActivityFeed'
import type { ActivityItem } from '@/api/types/analytics'

const FIXED_BASE = new Date('2026-03-26T12:00:00.000Z')

function makeActivities(count: number): ActivityItem[] {
  const eventTypes = ['task.created', 'task.updated', 'agent.status_changed', 'budget.record_added', 'approval.submitted'] as const
  const agents = ['agent-cto', 'agent-eng-lead', 'agent-designer', 'agent-qa', 'agent-devops'] as const
  return Array.from({ length: count }, (_, i) => ({
    id: `activity-${i}`,
    timestamp: new Date(FIXED_BASE.getTime() - i * 120_000).toISOString(),
    agent_name: agents[i % agents.length]!,
    action_type: eventTypes[i % eventTypes.length]!,
    description: `Performed action #${i + 1}`,
    task_id: i % 3 === 0 ? `task-${100 + i}` : null,
    department: i % 2 === 0 ? ('engineering' as const) : null,
  }))
}

const meta = {
  title: 'Dashboard/ActivityFeed',
  component: ActivityFeed,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <MemoryRouter>
        <div className="max-w-md">
          <Story />
        </div>
      </MemoryRouter>
    ),
  ],
} satisfies Meta<typeof ActivityFeed>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { activities: makeActivities(5) },
}

export const Empty: Story = {
  args: { activities: [] },
}

export const Full: Story = {
  args: { activities: makeActivities(15) },
}
