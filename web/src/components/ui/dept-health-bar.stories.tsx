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
  args: { name: 'Engineering', health: 92, agentCount: 5 },
}

export const Moderate: Story = {
  args: { name: 'Marketing', health: 55, agentCount: 3 },
}

export const Warning: Story = {
  args: { name: 'Sales', health: 30, agentCount: 2 },
}

export const Critical: Story = {
  args: { name: 'Support', health: 12, agentCount: 1 },
}

export const Full: Story = {
  args: { name: 'Operations', health: 100, agentCount: 8 },
}

export const Empty: Story = {
  args: { name: 'New Dept', health: 0, agentCount: 0 },
}

export const AllHealthLevels: Story = {
  args: { name: 'Engineering', health: 92, agentCount: 5 },
  render: () => (
    <div className="flex max-w-sm flex-col gap-4">
      <DeptHealthBar name="Engineering" health={92} agentCount={5} />
      <DeptHealthBar name="Marketing" health={65} agentCount={3} />
      <DeptHealthBar name="Sales" health={38} agentCount={2} />
      <DeptHealthBar name="Support" health={15} agentCount={1} />
    </div>
  ),
}
