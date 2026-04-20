import type { Meta, StoryObj } from '@storybook/react'
import { fn } from 'storybook/test'
import { TaskDeleteDialog } from './TaskDeleteDialog'

const meta = {
  title: 'Pages/Tasks/TaskDeleteDialog',
  component: TaskDeleteDialog,
  args: {
    onOpenChange: fn(),
    onConfirm: fn(),
  },
} satisfies Meta<typeof TaskDeleteDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {
  args: { open: true },
}

export const Closed: Story = {
  args: { open: false },
}
