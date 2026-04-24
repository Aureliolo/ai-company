import type { ReactElement } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Trash2 } from 'lucide-react'
import { AnimatePresence } from 'motion/react'
import { Button } from '@/components/ui/button'
import { BulkActionBar } from './bulk-action-bar'

const meta = {
  title: 'Feedback/BulkActionBar',
  component: BulkActionBar,
  tags: ['autodocs'],
  parameters: { layout: 'fullscreen', a11y: { test: 'error' } },
} satisfies Meta<typeof BulkActionBar>

export default meta
type Story = StoryObj<typeof meta>

function withFakeList(Story: () => ReactElement) {
  return (
    <div className="relative h-[50vh] w-full bg-background p-section-gap">
      <p className="text-sm text-muted-foreground">
        Imagine a selectable list view above this viewport.
      </p>
      <AnimatePresence>
        <Story />
      </AnimatePresence>
    </div>
  )
}

export const Default: Story = {
  args: {
    selectedCount: 3,
    onClear: () => {},
    children: (
      <Button
        size="sm"
        variant="outline"
        className="gap-1 border-danger/30 text-danger hover:bg-danger/10"
      >
        <Trash2 className="size-3.5" /> Delete 3
      </Button>
    ),
  },
  decorators: [(Story) => withFakeList(Story)],
}

export const SingleSelection: Story = {
  args: {
    selectedCount: 1,
    onClear: () => {},
    children: (
      <Button size="sm" variant="outline" className="gap-1 border-danger/30 text-danger">
        <Trash2 className="size-3.5" /> Delete 1
      </Button>
    ),
  },
  decorators: [(Story) => withFakeList(Story)],
}

export const Loading: Story = {
  args: {
    selectedCount: 5,
    onClear: () => {},
    loading: true,
    children: (
      <Button size="sm" variant="outline" className="gap-1 border-danger/30 text-danger" disabled>
        <Trash2 className="size-3.5" /> Delete 5
      </Button>
    ),
  },
  decorators: [(Story) => withFakeList(Story)],
}
