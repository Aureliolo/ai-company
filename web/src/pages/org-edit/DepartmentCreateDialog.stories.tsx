import type { Meta, StoryObj } from '@storybook/react'
import type { Department } from '@/api/types/org'
import { DepartmentCreateDialog } from './DepartmentCreateDialog'

const MOCK_DEPARTMENT: Department = {
  name: 'engineering',
  display_name: 'Engineering',
  teams: [],
  head: null,
  budget_percent: 0,
}

const meta = {
  title: 'OrgEdit/DepartmentCreateDialog',
  component: DepartmentCreateDialog,
  parameters: {
    a11y: { test: 'error' },
  },
  args: {
    open: true,
    onOpenChange: () => {},
    onCreate: async () => MOCK_DEPARTMENT,
  },
} satisfies Meta<typeof DepartmentCreateDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {}

export const Closed: Story = {
  args: { open: false },
}
