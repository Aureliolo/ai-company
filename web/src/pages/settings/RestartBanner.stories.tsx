import type { Meta, StoryObj } from '@storybook/react'
import { RestartBanner } from './RestartBanner'

const meta: Meta<typeof RestartBanner> = {
  title: 'Settings/RestartBanner',
  component: RestartBanner,
}
export default meta

type Story = StoryObj<typeof RestartBanner>

export const Singular: Story = {
  args: { count: 1, onDismiss: () => {} },
}

export const Plural: Story = {
  args: { count: 3, onDismiss: () => {} },
}

export const Hidden: Story = {
  args: { count: 0, onDismiss: () => {} },
}
