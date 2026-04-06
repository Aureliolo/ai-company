import type { Meta, StoryObj } from '@storybook/react-vite'

import { NotificationsSection } from './NotificationsSection'

const meta = {
  title: 'Settings/NotificationsSection',
  component: NotificationsSection,
} satisfies Meta<typeof NotificationsSection>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
