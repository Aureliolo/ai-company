import type { Meta, StoryObj } from '@storybook/react'
import { AlertCircle, Inbox, Search, Users } from 'lucide-react'
import { EmptyState } from './empty-state'

const meta = {
  title: 'Feedback/EmptyState',
  component: EmptyState,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
} satisfies Meta<typeof EmptyState>

export default meta
type Story = StoryObj<typeof meta>

export const NoData: Story = {
  args: {
    icon: Inbox,
    title: 'No agents found',
    description: 'Your organization has no agents yet. Create one to get started.',
  },
}

export const NoResults: Story = {
  args: {
    icon: Search,
    title: 'No results',
    description: 'Try adjusting your search or filter criteria.',
  },
}

export const WithAction: Story = {
  args: {
    icon: Users,
    title: 'No agents found',
    description: 'Create your first agent to start building your organization.',
    action: {
      label: 'Create Agent',
      onClick: () => {},
    },
  },
}

export const ErrorVariant: Story = {
  args: {
    icon: AlertCircle,
    title: 'Failed to load data',
    description: 'Something went wrong. Please try again.',
    action: {
      label: 'Retry',
      onClick: () => {},
    },
  },
}

export const Minimal: Story = {
  args: {
    title: 'Nothing here yet',
  },
}
