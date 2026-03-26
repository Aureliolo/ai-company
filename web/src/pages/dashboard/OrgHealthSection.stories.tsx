import type { Meta, StoryObj } from '@storybook/react'
import { OrgHealthSection } from './OrgHealthSection'
import type { DepartmentHealth, DepartmentName } from '@/api/types'

function makeDepts(configs: Array<{ name: DepartmentName; health: number }>): DepartmentHealth[] {
  return configs.map((c, i) => ({
    name: c.name,
    display_name: c.name.charAt(0).toUpperCase() + c.name.slice(1).replace('_', ' '),
    health_percent: c.health,
    agent_count: 2 + i,
    task_count: 5 + i * 2,
    cost_usd: null,
  }))
}

const meta = {
  title: 'Dashboard/OrgHealthSection',
  component: OrgHealthSection,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="max-w-md">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof OrgHealthSection>

export default meta
type Story = StoryObj<typeof meta>

export const Healthy: Story = {
  args: {
    departments: makeDepts([
      { name: 'engineering', health: 92 },
      { name: 'design', health: 85 },
      { name: 'product', health: 78 },
    ]),
    overallHealth: 85,
  },
}

export const Mixed: Story = {
  args: {
    departments: makeDepts([
      { name: 'engineering', health: 90 },
      { name: 'design', health: 45 },
      { name: 'operations', health: 20 },
      { name: 'security', health: 70 },
    ]),
    overallHealth: 56,
  },
}

export const Empty: Story = {
  args: { departments: [], overallHealth: null },
}
