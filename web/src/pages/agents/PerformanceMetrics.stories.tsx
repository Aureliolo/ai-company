import type { Meta, StoryObj } from '@storybook/react'
import { PerformanceMetrics } from './PerformanceMetrics'

const meta = {
  title: 'Agents/PerformanceMetrics',
  component: PerformanceMetrics,
  decorators: [(Story) => <div className="p-6 max-w-2xl"><Story /></div>],
} satisfies Meta<typeof PerformanceMetrics>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    cards: [
      { label: 'TASKS COMPLETED', value: 127, subText: '12 this week', sparklineData: [10, 12, 8, 15, 12] },
      { label: 'AVG COMPLETION TIME', value: '1h 0m' },
      { label: 'SUCCESS RATE', value: '94.0%', subText: 'across 45 tasks (30d)' },
      { label: 'COST PER TASK', value: '$0.35' },
    ],
  },
}

export const NullValues: Story = {
  args: {
    cards: [
      { label: 'TASKS COMPLETED', value: 0, subText: '0 this week' },
      { label: 'AVG COMPLETION TIME', value: '--' },
      { label: 'SUCCESS RATE', value: '--' },
      { label: 'COST PER TASK', value: '--' },
    ],
  },
}

export const Empty: Story = {
  args: { cards: [] },
}
