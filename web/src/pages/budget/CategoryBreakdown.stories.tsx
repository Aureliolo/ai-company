import type { Meta, StoryObj } from '@storybook/react'
import { CategoryBreakdown } from './CategoryBreakdown'
import type { CategoryRatio } from '@/utils/budget'

const BALANCED: CategoryRatio = {
  productive: { cost: 33, percent: 33.0, count: 12 },
  coordination: { cost: 33, percent: 33.0, count: 10 },
  system: { cost: 34, percent: 34.0, count: 14 },
  uncategorized: { cost: 0, percent: 0, count: 0 },
}

const PRODUCTIVE_HEAVY: CategoryRatio = {
  productive: { cost: 80, percent: 80.0, count: 25 },
  coordination: { cost: 10, percent: 10.0, count: 5 },
  system: { cost: 8, percent: 8.0, count: 4 },
  uncategorized: { cost: 2, percent: 2.0, count: 1 },
}

const HIGH_COORDINATION: CategoryRatio = {
  productive: { cost: 30, percent: 30.0, count: 10 },
  coordination: { cost: 40, percent: 40.0, count: 15 },
  system: { cost: 20, percent: 20.0, count: 8 },
  uncategorized: { cost: 10, percent: 10.0, count: 3 },
}

const EMPTY: CategoryRatio = {
  productive: { cost: 0, percent: 0, count: 0 },
  coordination: { cost: 0, percent: 0, count: 0 },
  system: { cost: 0, percent: 0, count: 0 },
  uncategorized: { cost: 0, percent: 0, count: 0 },
}

const meta = {
  title: 'Budget/CategoryBreakdown',
  component: CategoryBreakdown,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="max-w-md">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof CategoryBreakdown>

export default meta
type Story = StoryObj<typeof meta>

export const Balanced: Story = {
  args: {
    ratio: BALANCED,
  },
}

export const ProductiveHeavy: Story = {
  args: {
    ratio: PRODUCTIVE_HEAVY,
  },
}

export const HighCoordination: Story = {
  args: {
    ratio: HIGH_COORDINATION,
  },
}

export const Empty: Story = {
  args: {
    ratio: EMPTY,
  },
}
