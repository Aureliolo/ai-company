import type { Meta, StoryObj } from '@storybook/react'
import { DeptHealthBar } from './dept-health-bar'

const meta = {
  title: 'UI/DeptHealthBar',
  component: DeptHealthBar,
  tags: ['autodocs'],
  argTypes: {
    health: { control: { type: 'range', min: 0, max: 100 } },
  },
} satisfies Meta<typeof DeptHealthBar>

export default meta
type Story = StoryObj<typeof meta>

export const Healthy: Story = {
  args: { name: 'Engineering', health: 92, agentCount: 5, taskCount: 18 },
}

export const Moderate: Story = {
  args: { name: 'Marketing', health: 55, agentCount: 3, taskCount: 8 },
}

export const Warning: Story = {
  args: { name: 'Sales', health: 30, agentCount: 2, taskCount: 4 },
}

export const Critical: Story = {
  args: { name: 'Support', health: 12, agentCount: 1, taskCount: 2 },
}

export const Full: Story = {
  args: { name: 'Operations', health: 100, agentCount: 8, taskCount: 25 },
}

export const Empty: Story = {
  args: { name: 'New Dept', health: 0, agentCount: 0, taskCount: 0 },
}

export const AllHealthLevels: Story = {
  args: { name: 'Engineering', health: 92, agentCount: 5, taskCount: 18 },
  render: () => (
    <div className="flex max-w-sm flex-col gap-4">
      <DeptHealthBar name="Engineering" health={92} agentCount={5} taskCount={18} />
      <DeptHealthBar name="Marketing" health={65} agentCount={3} taskCount={8} />
      <DeptHealthBar name="Sales" health={38} agentCount={2} taskCount={4} />
      <DeptHealthBar name="Support" health={15} agentCount={1} taskCount={2} />
    </div>
  ),
}
