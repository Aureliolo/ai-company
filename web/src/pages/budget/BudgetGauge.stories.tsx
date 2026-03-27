import type { Meta, StoryObj } from '@storybook/react'
import { BudgetGauge } from './BudgetGauge'

const meta = {
  title: 'Budget/BudgetGauge',
  component: BudgetGauge,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="max-w-xs">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof BudgetGauge>

export default meta
type Story = StoryObj<typeof meta>

export const Healthy: Story = {
  args: {
    usedPercent: 20,
    budgetRemaining: 400,
    daysUntilExhausted: null,
  },
}

export const Warning: Story = {
  args: {
    usedPercent: 65,
    budgetRemaining: 175,
    daysUntilExhausted: 12,
  },
}

export const Critical: Story = {
  args: {
    usedPercent: 95,
    budgetRemaining: 25,
    daysUntilExhausted: 2,
  },
}

export const Exhausted: Story = {
  args: {
    usedPercent: 100,
    budgetRemaining: 0,
    daysUntilExhausted: 0,
  },
}
