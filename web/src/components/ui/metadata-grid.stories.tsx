import type { Meta, StoryObj } from '@storybook/react'
import { MetadataGrid } from './metadata-grid'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import { formatCurrency } from '@/utils/format'

const SAMPLE_COST = formatCurrency(12.5, DEFAULT_CURRENCY)

const meta = {
  title: 'UI/MetadataGrid',
  component: MetadataGrid,
  tags: ['autodocs'],
} satisfies Meta<typeof MetadataGrid>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    items: [
      { label: 'Type', value: 'Development' },
      { label: 'Priority', value: 'High' },
      { label: 'Status', value: 'Active' },
    ],
  },
}

export const TwoColumns: Story = {
  args: {
    columns: 2,
    items: [
      { label: 'Created', value: 'Mar 31, 2026' },
      { label: 'Updated', value: '2 hours ago' },
    ],
  },
}

export const FourColumns: Story = {
  args: {
    columns: 4,
    items: [
      { label: 'Type', value: 'Code' },
      { label: 'Size', value: '1.2 MB', valueClassName: 'font-mono text-xs' },
      { label: 'Content Type', value: 'application/json' },
      { label: 'Created', value: 'Mar 31, 2026' },
    ],
  },
}

export const WithMonoValues: Story = {
  args: {
    items: [
      { label: 'Cost', value: SAMPLE_COST, valueClassName: 'font-mono text-xs' },
      { label: 'Tokens', value: '1,234', valueClassName: 'font-mono text-xs' },
      { label: 'Duration', value: '2m 30s', valueClassName: 'font-mono text-xs' },
    ],
  },
}

export const SingleItem: Story = {
  args: {
    items: [{ label: 'Status', value: 'Active' }],
  },
}

export const ManyItems: Story = {
  args: {
    columns: 3,
    items: [
      { label: 'Type', value: 'Development' },
      { label: 'Priority', value: 'High' },
      { label: 'Status', value: 'Active' },
      { label: 'Size', value: '1.2 MB', valueClassName: 'font-mono text-xs' },
      { label: 'Created', value: 'Mar 31, 2026' },
      { label: 'Updated', value: '2 hours ago' },
      { label: 'Owner', value: 'agent-eng-001' },
      { label: 'Cost', value: SAMPLE_COST, valueClassName: 'font-mono text-xs' },
      { label: 'Duration', value: '2m 30s', valueClassName: 'font-mono text-xs' },
    ],
  },
}

export const Empty: Story = {
  args: { items: [] },
}
