import type { Meta, StoryObj } from '@storybook/react'
import { Sparkline } from './sparkline'

const meta = {
  title: 'UI/Sparkline',
  component: Sparkline,
  tags: ['autodocs'],
  argTypes: {
    color: { control: 'color' },
    width: { control: { type: 'number', min: 32, max: 200 } },
    height: { control: { type: 'number', min: 16, max: 100 } },
  },
} satisfies Meta<typeof Sparkline>

export default meta
type Story = StoryObj<typeof meta>

const RISING_DATA = [12, 15, 13, 18, 22, 19, 25, 28, 24, 30]
const FALLING_DATA = [30, 28, 25, 22, 18, 20, 15, 12, 10, 8]
const VOLATILE_DATA = [10, 25, 8, 30, 12, 28, 5, 22, 15, 20]
const FLAT_DATA = [15, 15, 16, 15, 14, 15, 16, 15, 15, 15]

export const Default: Story = {
  args: { data: RISING_DATA },
}

export const Rising: Story = {
  args: { data: RISING_DATA, color: 'var(--so-success)' },
}

export const Falling: Story = {
  args: { data: FALLING_DATA, color: 'var(--so-danger)' },
}

export const Volatile: Story = {
  args: { data: VOLATILE_DATA, color: 'var(--so-warning)' },
}

export const Flat: Story = {
  args: { data: FLAT_DATA },
}

export const MetricCardSize: Story = {
  args: { data: RISING_DATA, width: 60, height: 28 },
}

export const Empty: Story = {
  args: { data: [] },
}

export const AllTrends: Story = {
  args: { data: RISING_DATA },
  render: () => (
    <div className="flex items-center gap-6">
      <Sparkline data={RISING_DATA} color="var(--so-success)" />
      <Sparkline data={FLAT_DATA} color="var(--so-accent)" />
      <Sparkline data={VOLATILE_DATA} color="var(--so-warning)" />
      <Sparkline data={FALLING_DATA} color="var(--so-danger)" />
    </div>
  ),
}
