import type { Meta, StoryObj } from '@storybook/react'
import { DepartmentEditDrawer } from './DepartmentEditDrawer'
import type { Department, DepartmentHealth } from '@/api/types'

const mockDept: Department = {
  name: 'engineering',
  display_name: 'Engineering',
  teams: [
    { name: 'Backend', members: ['alice', 'bob'] },
    { name: 'Frontend', members: ['carol'] },
  ],
}

const mockHealth: DepartmentHealth = {
  department_name: 'engineering',
  agent_count: 3,
  active_agent_count: 2,
  currency: 'EUR',
  avg_performance_score: 7.5,
  department_cost_7d: 25.5,
  cost_trend: [],
  collaboration_score: 6.0,
  utilization_percent: 85,
}

const meta = {
  title: 'OrgEdit/DepartmentEditDrawer',
  component: DepartmentEditDrawer,
  parameters: {
    a11y: { test: 'error' },
  },
  args: {
    open: true,
    onClose: () => {},
    department: mockDept,
    health: mockHealth,
    onUpdate: async () => mockDept,
    onDelete: async () => {},
    saving: false,
  },
} satisfies Meta<typeof DepartmentEditDrawer>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {}

export const NoHealthData: Story = {
  args: { health: null },
}

export const Saving: Story = {
  args: { saving: true },
}
