import type { Meta, StoryObj } from '@storybook/react'
import { ProseInsight } from './ProseInsight'

const meta = {
  title: 'Agents/ProseInsight',
  component: ProseInsight,
  decorators: [(Story) => <div className="p-6 max-w-lg"><Story /></div>],
} satisfies Meta<typeof ProseInsight>

export default meta
type Story = StoryObj<typeof meta>

export const SingleInsight: Story = {
  args: { insights: ['Success rate of 94.0% across 127 completed tasks.'] },
}

export const MultipleInsights: Story = {
  args: {
    insights: [
      'Success rate of 94.0% across 127 completed tasks.',
      'Performance trending upward over the recent window.',
      'Quality score of 8.2/10 -- consistently high output.',
    ],
  },
}

export const Empty: Story = {
  args: { insights: [] },
}
