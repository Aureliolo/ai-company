import type { Meta, StoryObj } from '@storybook/react'
import { TaskCreateDialog } from './TaskCreateDialog'

const meta = {
  title: 'Tasks/TaskCreateDialog',
  component: TaskCreateDialog,
  tags: ['autodocs'],
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof TaskCreateDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {
  args: {
    open: true,
    onOpenChange: () => {},
    onCreate: async (data) => { console.log('Create:', data) },
  },
}

export const Closed: Story = {
  args: {
    open: false,
    onOpenChange: () => {},
    onCreate: async () => {},
  },
}
