import type { Meta, StoryObj } from '@storybook/react'
import { ProgressGauge } from './progress-gauge'

const meta = {
  title: 'UI/ProgressGauge',
  component: ProgressGauge,
  tags: ['autodocs'],
  argTypes: {
    value: { control: { type: 'range', min: 0, max: 100 } },
    max: { control: { type: 'number', min: 1 } },
    variant: { control: 'select', options: ['circular', 'linear'] },
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

export const LinearDefault: Story = {
  args: { value: 75, variant: 'linear' },
}

export const LinearWithLabel: Story = {
  args: { value: 60, variant: 'linear', label: 'Budget' },
}

export const LinearLow: Story = {
  args: { value: 15, variant: 'linear', label: 'Critical' },
}

export const LinearHigh: Story = {
  args: { value: 92, variant: 'linear', label: 'Healthy' },
}

export const LinearSmall: Story = {
  args: { value: 68, variant: 'linear', size: 'sm', label: 'CPU' },
}

export const LinearAllThresholds: Story = {
  args: { value: 50 },
  render: () => (
    <div className="flex flex-col gap-4 w-64">
      <ProgressGauge value={10} variant="linear" label="Danger" />
      <ProgressGauge value={35} variant="linear" label="Warning" />
      <ProgressGauge value={60} variant="linear" label="Accent" />
      <ProgressGauge value={90} variant="linear" label="Success" />
    </div>
  ),
}

export const BothVariants: Story = {
  args: { value: 65 },
  render: () => (
    <div className="flex items-start gap-8">
      <ProgressGauge value={65} label="Circular" />
      <div className="w-48">
        <ProgressGauge value={65} variant="linear" label="Linear" />
      </div>
    </div>
  ),
}
