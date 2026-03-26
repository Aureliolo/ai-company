import type { Meta, StoryObj } from '@storybook/react'
import { StatPill } from './stat-pill'

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
      <StatPill label="Spend" value="$12.50" />
    </div>
  ),
}
