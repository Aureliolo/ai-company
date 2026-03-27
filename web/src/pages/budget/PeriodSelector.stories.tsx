import type { Meta, StoryObj } from '@storybook/react'
import { action } from 'storybook/actions'
import { PeriodSelector } from './PeriodSelector'

const meta = {
  title: 'Budget/PeriodSelector',
  component: PeriodSelector,
  tags: ['autodocs'],
  parameters: { a11y: { test: 'error' } },
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
    onChange: action('onChange'),
  },
}

export const Daily: Story = {
  args: {
    value: 'daily',
    onChange: action('onChange'),
  },
}

export const Weekly: Story = {
  args: {
    value: 'weekly',
    onChange: action('onChange'),
  },
}
