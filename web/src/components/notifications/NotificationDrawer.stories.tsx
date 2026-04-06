import type { Meta, StoryObj } from '@storybook/react-vite'
import { useEffect } from 'react'
import { MemoryRouter } from 'react-router'

import { useNotificationsStore } from '@/stores/notifications'

import { NotificationDrawer } from './NotificationDrawer'

const meta = {
  title: 'Notifications/NotificationDrawer',
  component: NotificationDrawer,
  decorators: [
    (Story) => (
      <MemoryRouter>
        <Story />
      </MemoryRouter>
    ),
  ],
  args: {
    open: true,
    onClose: () => {},
  },
} satisfies Meta<typeof NotificationDrawer>

export default meta
type Story = StoryObj<typeof meta>

export const Empty: Story = {}

function SeedNotifications({ children }: { readonly children: React.ReactNode }) {
  useEffect(() => {
    const { enqueue } = useNotificationsStore.getState()
    enqueue({
      category: 'approvals.pending',
      title: 'Approval requested for agent deployment',
      description: 'Engineering department needs approval',
      href: '/approvals',
    })
    enqueue({
      category: 'budget.threshold',
      title: 'Budget threshold crossed',
      description: 'Monthly spend reached 80% of limit',
      severity: 'warning',
    })
    enqueue({
      category: 'tasks.failed',
      title: 'Task failed: Code review',
      severity: 'error',
    })
    enqueue({
      category: 'agents.hired',
      title: 'Agent hired: Marketing Writer',
    })
  }, [])
  return <>{children}</>
}

export const WithItems: Story = {
  decorators: [
    (Story) => (
      <SeedNotifications>
        <Story />
      </SeedNotifications>
    ),
  ],
  args: {
    open: true,
  },
}
