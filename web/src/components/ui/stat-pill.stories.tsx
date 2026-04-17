import type { Meta, StoryObj } from '@storybook/react'
import { StatPill } from './stat-pill'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import { formatCurrency } from '@/utils/format'

const SAMPLE_SPEND = formatCurrency(12.5, DEFAULT_CURRENCY)

const meta = {
  title: 'UI/StatPill',
  component: StatPill,
  tags: ['autodocs'],
} satisfies Meta<typeof StatPill>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { label: 'Tasks', value: 42 },
}

export const StringValue: Story = {
  args: { label: 'Status', value: 'OK' },
}

export const LargeNumber: Story = {
  args: { label: 'Tokens', value: '1.2M' },
}

export const ZeroValue: Story = {
  args: { label: 'Errors', value: 0 },
}

export const Multiple: Story = {
  args: { label: 'Agents', value: 8 },
  render: () => (
    <div className="flex flex-wrap gap-2">
      <StatPill label="Agents" value={8} />
      <StatPill label="Active" value={5} />
      <StatPill label="Tasks" value={24} />
      <StatPill label="Spend" value={SAMPLE_SPEND} />
    </div>
  ),
}
