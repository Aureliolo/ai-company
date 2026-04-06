import type { Meta, StoryObj } from '@storybook/react-vite'

import { NotificationEmptyState } from './NotificationEmptyState'

const meta = {
  title: 'Notifications/NotificationEmptyState',
  component: NotificationEmptyState,
  args: {
    filter: 'all',
  },
} satisfies Meta<typeof NotificationEmptyState>

export default meta
type Story = StoryObj<typeof meta>

export const AllFilter: Story = {}

export const ApprovalsFilter: Story = {
  args: { filter: 'approvals' },
}

export const BudgetFilter: Story = {
  args: { filter: 'budget' },
}

export const SystemFilter: Story = {
  args: { filter: 'system' },
}

export const TasksFilter: Story = {
  args: { filter: 'tasks' },
}

export const AgentsFilter: Story = {
  args: { filter: 'agents' },
}

export const ProvidersFilter: Story = {
  args: { filter: 'providers' },
}

export const ConnectionFilter: Story = {
  args: { filter: 'connection' },
}
