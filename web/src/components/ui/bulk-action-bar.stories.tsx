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

/**
 * Visual snapshot of the destructive action in its hover state. The bar
 * itself has no interactive surface of its own -- the hover comes from
 * the caller-supplied button slot. Story pins the hover parameter so
 * Chromatic/Storybook interaction tests trigger the destructive button
 * hover styles.
 */
export const Hover: Story = {
  args: {
    selectedCount: 3,
    onClear: () => {},
    children: (
      <Button
        size="sm"
        variant="outline"
        className="gap-1 border-danger/30 bg-danger/10 text-danger"
        data-hovered="true"
      >
        <Trash2 className="size-3.5" /> Delete 3
      </Button>
    ),
  },
  parameters: { pseudo: { hover: true } },
  decorators: [(Story) => withFakeList(Story)],
}

/**
 * Batch op surfaced a failure. The action slot goes to the error treatment
 * (solid destructive fill) while the bar stays visible so the user can
 * retry from the same toolbar. Real callers pair this with an
 * `<ErrorBanner>` on the list surface; the story only illustrates the
 * button appearance.
 */
export const Error: Story = {
  args: {
    selectedCount: 3,
    onClear: () => {},
    children: (
      <Button
        size="sm"
        className="gap-1 bg-danger text-danger-foreground hover:bg-danger/90"
      >
        <Trash2 className="size-3.5" /> Retry delete 3
      </Button>
    ),
  },
  decorators: [(Story) => withFakeList(Story)],
}

/**
 * Empty selection -- the bar renders "0 selected" with a disabled
 * destructive button. In practice the page should unmount the bar via
 * `AnimatePresence` when `selectedCount === 0`; this story documents the
 * degenerate state for visual review.
 */
export const Empty: Story = {
  args: {
    selectedCount: 0,
    onClear: () => {},
    children: (
      <Button
        size="sm"
        variant="outline"
        className="gap-1 border-danger/30 text-danger"
        disabled
      >
        <Trash2 className="size-3.5" /> Delete 0
      </Button>
    ),
  },
  decorators: [(Story) => withFakeList(Story)],
}
