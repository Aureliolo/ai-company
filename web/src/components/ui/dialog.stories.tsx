import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { Button } from './button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogCloseButton,
} from './dialog'

function DialogDemo({ open: initialOpen = true }: { open?: boolean }) {
  const [open, setOpen] = useState(initialOpen)
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open Dialog</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <div>
              <DialogTitle>Dialog Title</DialogTitle>
              <DialogDescription>
                This is a description of the dialog content.
              </DialogDescription>
            </div>
            <DialogCloseButton />
          </DialogHeader>
          <div className="px-6 py-4">
            <p className="text-sm text-foreground">Dialog body content goes here.</p>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

const meta = {
  title: 'UI/Dialog',
  component: DialogDemo,
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof DialogDemo>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const Closed: Story = {
  args: {
    open: false,
  },
}
