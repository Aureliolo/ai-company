import type { Meta, StoryObj } from '@storybook/react'
import { DepartmentCreateDialog } from './DepartmentCreateDialog'
import type { Department } from '@/api/types'

const stubDept: Department = {
  name: 'engineering',
  display_name: 'New Department',
  teams: [],
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
    existingNames: ['engineering', 'product'],
    onCreate: async () => stubDept,
  },
} satisfies Meta<typeof DepartmentCreateDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {}

export const Closed: Story = {
  args: { open: false },
}
