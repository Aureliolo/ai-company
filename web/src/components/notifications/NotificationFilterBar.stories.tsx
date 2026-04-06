import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'

import type { NotificationFilterGroup } from '@/types/notifications'

import { NotificationFilterBar } from './NotificationFilterBar'

function FilterBarWrapper() {
  const [value, setValue] = useState<NotificationFilterGroup>('all')
  return <NotificationFilterBar value={value} onChange={setValue} />
}

const meta = {
  title: 'Notifications/NotificationFilterBar',
  component: NotificationFilterBar,
  args: {
    value: 'all',
    onChange: () => {},
  },
} satisfies Meta<typeof NotificationFilterBar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const Interactive: Story = {
  render: () => <FilterBarWrapper />,
}

export const BudgetSelected: Story = {
  args: {
    value: 'budget',
  },
}
