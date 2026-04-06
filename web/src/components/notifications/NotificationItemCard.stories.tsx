import type { Meta, StoryObj } from '@storybook/react-vite'
import { MemoryRouter } from 'react-router'

import type { NotificationItem } from '@/types/notifications'

import { NotificationItemCard } from './NotificationItemCard'

const baseItem: NotificationItem = {
  id: '1',
  category: 'approvals.pending',
  severity: 'warning',
  title: 'Approval requested for agent deployment',
  description: 'Engineering department needs approval for new agent hire',
  timestamp: '2026-04-06T12:00:00.000Z',
  read: false,
  href: '/approvals',
  dispatchedTo: ['drawer', 'toast'],
}

const meta = {
  title: 'Notifications/NotificationItemCard',
  component: NotificationItemCard,
  decorators: [
    (Story) => (
      <MemoryRouter>
        <Story />
      </MemoryRouter>
    ),
  ],
  args: {
    item: baseItem,
    onMarkRead: () => {},
    onDismiss: () => {},
  },
} satisfies Meta<typeof NotificationItemCard>

export default meta
type Story = StoryObj<typeof meta>

export const Unread: Story = {}

export const Read: Story = {
  args: {
    item: { ...baseItem, read: true },
  },
}

export const InfoSeverity: Story = {
  args: {
    item: { ...baseItem, severity: 'info', category: 'agents.hired', title: 'Agent hired: Marketing Writer' },
  },
}

export const ErrorSeverity: Story = {
  args: {
    item: { ...baseItem, severity: 'error', category: 'system.error', title: 'System error occurred' },
  },
}

export const CriticalSeverity: Story = {
  args: {
    item: { ...baseItem, severity: 'critical', category: 'budget.exhausted', title: 'Monthly budget exhausted' },
  },
}

export const NoDescription: Story = {
  args: {
    item: { ...baseItem, description: undefined },
  },
}

export const NoHref: Story = {
  args: {
    item: { ...baseItem, href: undefined },
  },
}
