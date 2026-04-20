import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import type { TaskStatus } from '@/api/types/enums'
import { TaskTransitionDialog } from './TaskTransitionDialog'

const meta = {
  title: 'Pages/Tasks/TaskTransitionDialog',
  component: TaskTransitionDialog,
  parameters: { layout: 'centered' },
} satisfies Meta<typeof TaskTransitionDialog>

export default meta

type Story = StoryObj<typeof meta>

function Demo({ targetStatus }: { targetStatus: TaskStatus }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open dialog</Button>
      <TaskTransitionDialog
        open={open}
        targetStatus={targetStatus}
        transitioning={null}
        onOpenChange={setOpen}
        onConfirm={() => setOpen(false)}
      />
    </>
  )
}

export const Completed: Story = {
  args: {
    open: true,
    targetStatus: 'completed',
    transitioning: null,
    onOpenChange: () => {},
    onConfirm: () => {},
  },
  render: () => <Demo targetStatus="completed" />,
}

export const Rejected: Story = {
  args: {
    open: true,
    targetStatus: 'rejected',
    transitioning: null,
    onOpenChange: () => {},
    onConfirm: () => {},
  },
  render: () => <Demo targetStatus="rejected" />,
}
