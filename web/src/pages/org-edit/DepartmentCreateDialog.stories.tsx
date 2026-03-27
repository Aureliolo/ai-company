import type { Meta, StoryObj } from '@storybook/react'
import { DepartmentCreateDialog } from './DepartmentCreateDialog'

const meta = {
  title: 'OrgEdit/DepartmentCreateDialog',
  component: DepartmentCreateDialog,
  args: {
    open: true,
    onOpenChange: () => {},
    existingNames: ['engineering', 'product'],
    onCreate: async () => { throw new Error('Not implemented') },
  },
} satisfies Meta<typeof DepartmentCreateDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {}

export const Closed: Story = {
  args: { open: false },
}
