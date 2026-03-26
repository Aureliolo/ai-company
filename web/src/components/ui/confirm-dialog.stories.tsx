import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import { Button } from './button'
import { ConfirmDialog } from './confirm-dialog'

const meta = {
  title: 'Feedback/ConfirmDialog',
  component: ConfirmDialog,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof ConfirmDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    open: true,
    onOpenChange: () => {},
    title: 'Confirm action',
    description: 'Are you sure you want to proceed?',
    onConfirm: () => {},
  },
}

export const Destructive: Story = {
  args: {
    open: true,
    onOpenChange: () => {},
    title: 'Delete agent?',
    description: 'This action cannot be undone. The agent and all its data will be permanently removed.',
    variant: 'destructive',
    confirmLabel: 'Delete',
    onConfirm: () => {},
  },
}

export const Loading: Story = {
  args: {
    open: true,
    onOpenChange: () => {},
    title: 'Processing...',
    description: 'Please wait while we complete the action.',
    loading: true,
    onConfirm: () => {},
  },
}

function InteractiveDemo() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <Button onClick={() => setOpen(true)}>Open Dialog</Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Delete this agent?"
        description="This action cannot be undone."
        variant="destructive"
        confirmLabel="Delete"
        onConfirm={() => setOpen(false)}
      />
    </>
  )
}

export const Interactive: Story = {
  args: {
    open: false,
    onOpenChange: () => {},
    title: 'Interactive',
    onConfirm: () => {},
  },
  render: () => <InteractiveDemo />,
}
