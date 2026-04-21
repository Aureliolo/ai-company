import type { Meta, StoryObj } from '@storybook/react'
import { Slot } from './slot'

const meta = {
  title: 'Primitives/Slot',
  component: Slot,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component:
          'Local polymorphism primitive used exclusively by `<Button asChild>`. Clones its single child and merges props via Base UI `mergeProps`. Use Base UI `render` prop on Dialog / AlertDialog / Popover / Menu / Tabs / Drawer directly -- `<Slot>` is only here to preserve the `<Button asChild>` ergonomic.',
      },
    },
  },
} satisfies Meta<typeof Slot>

export default meta
type Story = StoryObj<typeof meta>

export const WithButton: Story = {
  args: {
    className: 'px-4 py-2 rounded-md bg-accent text-primary-foreground text-sm font-medium',
    children: <button type="button">Native button child</button>,
  },
}

export const WithLink: Story = {
  args: {
    className: 'inline-flex items-center gap-1 text-accent hover:underline',
    children: <a href="https://synthorg.io">Open docs</a>,
  },
}

export const WithDiv: Story = {
  args: {
    className: 'rounded-lg border border-border bg-card p-4 text-sm text-foreground',
    children: (
      <div>
        <p className="font-medium">Arbitrary child</p>
        <p className="mt-1 text-xs text-muted-foreground">Slot forwards className + props via merge-props.</p>
      </div>
    ),
  },
}

export const MergedClickHandlers: Story = {
  args: {
    className: 'px-3 py-2 rounded-md bg-accent/20 text-accent cursor-pointer',
    onClick: () => alert('Slot-level handler fired'),
    children: (
      <button type="button" onClick={() => alert('Child-level handler fired')}>Click me</button>
    ),
  },
  parameters: {
    docs: {
      description: {
        story: 'Slot and child click handlers are both invoked in order (Base UI `mergeProps` chains same-named event handlers).',
      },
    },
  },
}

export const InvalidChildLogsWarning: Story = {
  args: {
    className: 'text-muted-foreground',
    // Invalid: Slot expects exactly one element child. String children are
    // ignored (returned as-is) and a warning is logged.
    children: 'plain text child',
  },
  parameters: {
    docs: {
      description: {
        story: 'When the child is not a single React element, Slot returns it unchanged and logs a warning. No runtime error.',
      },
    },
  },
}
