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
  name: 'engineering',
  display_name: 'Engineering',
  health_percent: 85,
  agent_count: 3,
  task_count: 8,
  cost_usd: 25.5,
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
