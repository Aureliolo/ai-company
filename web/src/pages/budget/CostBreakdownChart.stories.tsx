import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { CostBreakdownChart } from './CostBreakdownChart'
import type { BreakdownDimension, BreakdownSlice } from '@/utils/budget'

const AGENT_SLICES: BreakdownSlice[] = [
  { key: 'agent-1', label: 'Alice Chen', cost: 120.5, percent: 28.3, color: 'var(--so-accent)' },
  { key: 'agent-2', label: 'Bob Smith', cost: 95.2, percent: 22.4, color: 'var(--so-success)' },
  { key: 'agent-3', label: 'Carol Jones', cost: 78.8, percent: 18.5, color: 'var(--so-warning)' },
  { key: 'agent-4', label: 'Dave Wilson', cost: 55.1, percent: 12.9, color: 'var(--so-danger)' },
  { key: 'agent-5', label: 'Eve Brown', cost: 42.3, percent: 9.9, color: 'var(--so-text-secondary)' },
  { key: 'agent-6', label: 'Frank Lee', cost: 33.7, percent: 8.0, color: 'var(--so-text-muted)' },
]

const DEPT_SLICES: BreakdownSlice[] = [
  { key: 'engineering', label: 'Engineering', cost: 220.5, percent: 51.8, color: 'var(--so-accent)' },
  { key: 'research', label: 'Research', cost: 105.2, percent: 24.7, color: 'var(--so-success)' },
  { key: 'design', label: 'Design', cost: 65.8, percent: 15.5, color: 'var(--so-warning)' },
  { key: 'operations', label: 'Operations', cost: 34.1, percent: 8.0, color: 'var(--so-danger)' },
]

const PROVIDER_SLICES: BreakdownSlice[] = [
  { key: 'provider-a', label: 'Provider A', cost: 280, percent: 65.9, color: 'var(--so-accent)' },
  { key: 'provider-b', label: 'Provider B', cost: 105, percent: 24.7, color: 'var(--so-success)' },
  { key: 'provider-c', label: 'Provider C', cost: 40, percent: 9.4, color: 'var(--so-warning)' },
]

const DIMENSION_DATA: Record<BreakdownDimension, BreakdownSlice[]> = {
  agent: AGENT_SLICES,
  department: DEPT_SLICES,
  provider: PROVIDER_SLICES,
}

function InteractiveBreakdown({
  initialDimension = 'agent',
  breakdown,
  ...rest
}: {
  initialDimension?: BreakdownDimension
  breakdown?: BreakdownSlice[]
  deptDisabled?: boolean
  currency?: string
}) {
  const [dimension, setDimension] = useState<BreakdownDimension>(initialDimension)
  const data = breakdown ?? DIMENSION_DATA[dimension]
  return (
    <CostBreakdownChart
      breakdown={data}
      dimension={dimension}
      onDimensionChange={setDimension}
      {...rest}
    />
  )
}

const meta = {
  title: 'Budget/CostBreakdownChart',
  component: CostBreakdownChart,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="max-w-md">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof CostBreakdownChart>

export default meta
type Story = StoryObj<typeof meta>

export const ByAgent: Story = {
  args: {
    breakdown: AGENT_SLICES,
    dimension: 'agent',
    onDimensionChange: () => {},
  },
  render: () => <InteractiveBreakdown initialDimension="agent" />,
}

export const ByDepartment: Story = {
  args: {
    breakdown: DEPT_SLICES,
    dimension: 'department',
    onDimensionChange: () => {},
  },
  render: () => <InteractiveBreakdown initialDimension="department" />,
}

export const ByProvider: Story = {
  args: {
    breakdown: PROVIDER_SLICES,
    dimension: 'provider',
    onDimensionChange: () => {},
  },
  render: () => <InteractiveBreakdown initialDimension="provider" />,
}

export const Empty: Story = {
  args: {
    breakdown: [],
    dimension: 'agent',
    onDimensionChange: () => {},
  },
}
