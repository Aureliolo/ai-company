import type { Meta, StoryObj } from '@storybook/react'
import { ProgressGauge } from './progress-gauge'

const meta = {
  title: 'UI/ProgressGauge',
  component: ProgressGauge,
  tags: ['autodocs'],
  argTypes: {
    value: { control: { type: 'range', min: 0, max: 100 } },
    max: { control: { type: 'number', min: 1 } },
    size: { control: 'select', options: ['sm', 'md'] },
  },
} satisfies Meta<typeof ProgressGauge>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { value: 75 },
}

export const WithLabel: Story = {
  args: { value: 60, label: 'Budget' },
}

export const Low: Story = {
  args: { value: 15, label: 'Critical' },
}

export const Medium: Story = {
  args: { value: 45, label: 'Moderate' },
}

export const High: Story = {
  args: { value: 92, label: 'Healthy' },
}

export const Small: Story = {
  args: { value: 68, size: 'sm', label: 'CPU' },
}

export const CustomMax: Story = {
  args: { value: 150, max: 200, label: 'Tokens' },
}

export const AllThresholds: Story = {
  args: { value: 50 },
  render: () => (
    <div className="flex items-end gap-8">
      <ProgressGauge value={10} label="Danger" />
      <ProgressGauge value={35} label="Warning" />
      <ProgressGauge value={60} label="Accent" />
      <ProgressGauge value={90} label="Success" />
    </div>
  ),
}
