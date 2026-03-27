import type { Meta, StoryObj } from '@storybook/react'
import { DepartmentStatsBar } from './DepartmentStatsBar'

const meta = {
  title: 'OrgChart/DepartmentStatsBar',
  component: DepartmentStatsBar,
  tags: ['autodocs'],
  parameters: {
    a11y: { test: 'error' },
  },
  decorators: [
    (Story) => (
      <div className="max-w-md">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof DepartmentStatsBar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    agentCount: 5,
    activeCount: 4,
    taskCount: 12,
    costUsd: 45.8,
  },
}

export const NoCost: Story = {
  args: {
    agentCount: 3,
    activeCount: 1,
    taskCount: 8,
    costUsd: null,
  },
}

export const ZeroActive: Story = {
  args: {
    agentCount: 2,
    activeCount: 0,
    taskCount: 0,
    costUsd: 0,
  },
}
