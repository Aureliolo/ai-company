import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import { LiveRegion } from './live-region'

const meta: Meta<typeof LiveRegion> = {
  title: 'UI/LiveRegion',
  component: LiveRegion,
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof LiveRegion>

export const Polite: Story = {
  args: {
    children: 'Status: 5 agents active',
    politeness: 'polite',
  },
}

export const Assertive: Story = {
  args: {
    children: 'Error: Connection lost',
    politeness: 'assertive',
    debounceMs: 0,
  },
}

export const DebouncedUpdates: Story = {
  render: function DebouncedUpdatesStory() {
    const [count, setCount] = useState(0)
    return (
      <div className="space-y-4">
        <button
          type="button"
          className="rounded bg-accent px-4 py-2 text-sm text-background"
          onClick={() => setCount((c) => c + 1)}
        >
          Simulate update ({count} clicks)
        </button>
        <LiveRegion politeness="polite" debounceMs={1000}>
          <span className="text-sm text-foreground">
            Tasks completed: {count} (announced after 1s debounce)
          </span>
        </LiveRegion>
      </div>
    )
  },
}
