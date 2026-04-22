import type { Meta, StoryObj } from '@storybook/react'
import { action } from 'storybook/actions'
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
    onClick: action('slot-level-handler'),
    children: (
      <button type="button" onClick={action('child-level-handler')}>Click me</button>
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

// Slot is a transparent merge helper, not a visual primitive, so loading /
// error / empty / hover states are carried by the child element, not by Slot
// itself. The stories below document each required state for shared-primitive
// coverage by wiring the child's visual state accordingly.

export const Hover: Story = {
  args: {
    className: 'px-4 py-2 rounded-md bg-accent text-primary-foreground text-sm font-medium hover:bg-accent/80',
    children: <button type="button">Hover me</button>,
  },
  parameters: {
    docs: {
      description: {
        story: 'Hover styling comes from the child element; Slot only merges className + props.',
      },
    },
  },
}

export const Loading: Story = {
  args: {
    className: 'px-4 py-2 rounded-md bg-muted text-muted-foreground text-sm cursor-wait',
    children: <button type="button" disabled>Loading...</button>,
  },
  parameters: {
    docs: {
      description: {
        story: 'Loading state: the child renders whatever loading affordance it carries; Slot forwards props as-is.',
      },
    },
  },
}

export const Error: Story = {
  args: {
    className: 'px-4 py-2 rounded-md bg-danger/10 text-danger text-sm',
    children: <button type="button">Try again</button>,
  },
  parameters: {
    docs: {
      description: {
        story: 'Error state: styling and copy come from the child; Slot has no error semantics of its own.',
      },
    },
  },
}

export const Empty: Story = {
  args: {
    className: 'text-muted-foreground',
    // N/A: Slot requires exactly one child element. An empty-state story for
    // Slot is documented by the behaviour shown in InvalidChildLogsWarning.
    children: null,
  },
  parameters: {
    docs: {
      description: {
        story: 'Not applicable: Slot requires exactly one child element. When `children` is null the story shows Slot rendering nothing (React elides falsy children).',
      },
    },
  },
}
