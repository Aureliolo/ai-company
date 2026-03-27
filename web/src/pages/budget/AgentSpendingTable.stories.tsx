import type { Meta, StoryObj } from '@storybook/react'
import { AgentSpendingTable } from './AgentSpendingTable'
import type { AgentSpendingRow } from '@/utils/budget'

const SIX_ROWS: AgentSpendingRow[] = [
  { agentId: 'a1', agentName: 'Alice Chen', totalCost: 45.2, budgetPercent: 30.1, taskCount: 12, costPerTask: 3.77 },
  { agentId: 'a2', agentName: 'Bob Rivera', totalCost: 32.8, budgetPercent: 21.9, taskCount: 8, costPerTask: 4.10 },
  { agentId: 'a3', agentName: 'Charlie Kim', totalCost: 28.5, budgetPercent: 19.0, taskCount: 15, costPerTask: 1.90 },
  { agentId: 'a4', agentName: 'Diana Patel', totalCost: 22.1, budgetPercent: 14.7, taskCount: 6, costPerTask: 3.68 },
  { agentId: 'a5', agentName: 'Eve Johansson', totalCost: 14.6, budgetPercent: 9.7, taskCount: 10, costPerTask: 1.46 },
  { agentId: 'a6', agentName: 'Frank Okafor', totalCost: 6.8, budgetPercent: 4.5, taskCount: 4, costPerTask: 1.70 },
]

const TWO_ROWS: AgentSpendingRow[] = [
  { agentId: 'a1', agentName: 'Alice Chen', totalCost: 80.5, budgetPercent: 67.1, taskCount: 20, costPerTask: 4.03 },
  { agentId: 'a2', agentName: 'Bob Rivera', totalCost: 39.5, budgetPercent: 32.9, taskCount: 12, costPerTask: 3.29 },
]

const meta = {
  title: 'Budget/AgentSpendingTable',
  component: AgentSpendingTable,
  tags: ['autodocs'],
  parameters: { a11y: { test: 'error' } },
  decorators: [
    (Story) => (
      <div className="max-w-3xl">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof AgentSpendingTable>

export default meta
type Story = StoryObj<typeof meta>

export const WithData: Story = {
  args: {
    rows: SIX_ROWS,
  },
}

export const FewAgents: Story = {
  args: {
    rows: TWO_ROWS,
  },
}

export const Empty: Story = {
  args: {
    rows: [],
  },
}
