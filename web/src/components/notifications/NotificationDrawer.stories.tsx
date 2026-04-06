import type { Meta, StoryObj } from '@storybook/react-vite'
import { MemoryRouter } from 'react-router'

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

export const WithItems: Story = {
  args: {
    open: true,
  },
}
