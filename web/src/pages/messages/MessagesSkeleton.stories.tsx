import type { Meta, StoryObj } from '@storybook/react'
import { MessagesSkeleton } from './MessagesSkeleton'

const meta: Meta<typeof MessagesSkeleton> = {
  title: 'Pages/Messages/MessagesSkeleton',
  component: MessagesSkeleton,
  parameters: { a11y: { test: 'error' } },
}
export default meta

type Story = StoryObj<typeof MessagesSkeleton>

export const Default: Story = {}
