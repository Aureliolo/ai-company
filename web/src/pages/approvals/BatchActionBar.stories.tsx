import type { Meta, StoryObj } from '@storybook/react'
import { fn } from 'storybook/test'
import { BatchActionBar } from './BatchActionBar'

const meta: Meta<typeof BatchActionBar> = {
  title: 'Pages/Approvals/BatchActionBar',
  component: BatchActionBar,
  parameters: {
    a11y: { test: 'error' },
  },
  args: {
    onApproveAll: fn(),
    onRejectAll: fn(),
    onClearSelection: fn(),
  },
  decorators: [(Story) => <div className="relative h-32"><Story /></div>],
}
export default meta

type Story = StoryObj<typeof BatchActionBar>

export const Default: Story = {
  args: { selectedCount: 3 },
}

export const SingleItem: Story = {
  args: { selectedCount: 1 },
}

export const ManyItems: Story = {
  args: { selectedCount: 12 },
}

export const Loading: Story = {
  args: { selectedCount: 5, loading: true },
}
