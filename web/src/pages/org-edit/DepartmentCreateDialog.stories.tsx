import type { Meta, StoryObj } from '@storybook/react'
import { DepartmentCreateDialog } from './DepartmentCreateDialog'

const meta = {
  title: 'OrgEdit/DepartmentCreateDialog',
  component: DepartmentCreateDialog,
  parameters: {
    a11y: { test: 'error' },
  },
  args: {
    open: true,
    onOpenChange: () => {},
  },
} satisfies Meta<typeof DepartmentCreateDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {}

export const Closed: Story = {
  args: { open: false },
}
