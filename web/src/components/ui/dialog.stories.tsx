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

function DialogWithLoading({ open: initialOpen = true }: { open?: boolean }) {
  const [open, setOpen] = useState(initialOpen)
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open Dialog</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <div>
              <DialogTitle>Loading</DialogTitle>
              <DialogDescription>Please wait while data is being loaded.</DialogDescription>
            </div>
            <DialogCloseButton />
          </DialogHeader>
          <div className="flex items-center justify-center px-6 py-8">
            <div className="size-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export const Loading: Story = {
  render: () => <DialogWithLoading />,
}

function DialogWithError({ open: initialOpen = true }: { open?: boolean }) {
  const [open, setOpen] = useState(initialOpen)
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open Dialog</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <div>
              <DialogTitle>Error</DialogTitle>
              <DialogDescription>Something went wrong.</DialogDescription>
            </div>
            <DialogCloseButton />
          </DialogHeader>
          <div className="px-6 py-4">
            <div className="rounded-md border border-danger/30 bg-danger/5 p-card text-sm text-danger">
              Failed to load data. Please try again.
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export const Error: Story = {
  render: () => <DialogWithError />,
}

function DialogWithForm({ open: initialOpen = true }: { open?: boolean }) {
  const [open, setOpen] = useState(initialOpen)
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open Dialog</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <div>
              <DialogTitle>Edit Name</DialogTitle>
              <DialogDescription>Enter a new name for this item.</DialogDescription>
            </div>
            <DialogCloseButton />
          </DialogHeader>
          <div className="flex flex-col gap-4 px-6 py-4">
            <input
              type="text"
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              placeholder="New name"
              defaultValue="My Workflow"
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={() => setOpen(false)}>Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export const WithForm: Story = {
  render: () => <DialogWithForm />,
}
