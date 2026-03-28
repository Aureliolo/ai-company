import type { Meta, StoryObj } from '@storybook/react'
import { RestartBadge } from './RestartBadge'

const meta = {
  title: 'Settings/RestartBadge',
  component: RestartBadge,
  parameters: { layout: 'centered' },
} satisfies Meta<typeof RestartBadge>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
