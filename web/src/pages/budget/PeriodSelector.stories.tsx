import type { Meta, StoryObj } from '@storybook/react'
import { PeriodSelector } from './PeriodSelector'

const meta = {
  title: 'Budget/PeriodSelector',
  component: PeriodSelector,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="max-w-xs">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof PeriodSelector>

export default meta
type Story = StoryObj<typeof meta>

export const Hourly: Story = {
  args: {
    value: 'hourly',
    onChange: () => {},
  },
}

export const Daily: Story = {
  args: {
    value: 'daily',
    onChange: () => {},
  },
}

export const Weekly: Story = {
  args: {
    value: 'weekly',
    onChange: () => {},
  },
}
