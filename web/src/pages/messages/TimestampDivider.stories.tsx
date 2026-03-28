import type { Meta, StoryObj } from '@storybook/react'
import { TimestampDivider } from './TimestampDivider'

const meta: Meta<typeof TimestampDivider> = {
  title: 'Pages/Messages/TimestampDivider',
  component: TimestampDivider,
  parameters: { a11y: { test: 'error' } },
  decorators: [(Story) => <div className="w-96"><Story /></div>],
}
export default meta

type Story = StoryObj<typeof TimestampDivider>

export const Today: Story = { args: { label: 'Today' } }
export const Yesterday: Story = { args: { label: 'Yesterday' } }
export const DateLabel: Story = { args: { label: 'Mar 15, 2026' } }
