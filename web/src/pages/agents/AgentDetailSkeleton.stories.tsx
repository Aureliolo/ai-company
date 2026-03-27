import type { Meta, StoryObj } from '@storybook/react'
import { AgentDetailSkeleton } from './AgentDetailSkeleton'

const meta = {
  title: 'Agents/AgentDetailSkeleton',
  component: AgentDetailSkeleton,
  decorators: [(Story) => <div className="p-6 max-w-4xl"><Story /></div>],
} satisfies Meta<typeof AgentDetailSkeleton>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
