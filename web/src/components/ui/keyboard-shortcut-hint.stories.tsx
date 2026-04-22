import type { Meta, StoryObj } from '@storybook/react'
import { KeyboardShortcutHint } from './keyboard-shortcut-hint'

const meta = {
  title: 'Overlays/KeyboardShortcutHint',
  component: KeyboardShortcutHint,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof KeyboardShortcutHint>

export default meta
type Story = StoryObj<typeof meta>

export const Single: Story = {
  args: { keys: ['/'] },
}

export const Chord: Story = {
  args: { keys: ['Ctrl', 'K'] },
}

export const WithLabel: Story = {
  args: { keys: ['/'], label: 'to search' },
}

export const MediumSize: Story = {
  args: { keys: ['Ctrl', 'Shift', 'P'], size: 'md', label: 'Open command palette' },
}

export const Sequence: Story = {
  args: { keys: ['g', 'g'], label: 'first item' },
}

// --- Canonical state matrix --------------------------------------------------
// KeyboardShortcutHint is a pure display primitive (no interactive state, no
// async fetches, no error surfaces of its own). Its "states" are carried by
// the content of the `keys` / `label` props rather than internal modes, so
// hover / loading / error / empty are expressed via representative content.

export const Hover: Story = {
  args: { keys: ['Ctrl', 'K'], label: 'Open palette' },
  parameters: {
    docs: {
      description: {
        story: 'Hover styling (if any) is inherited from the surrounding surface -- the component itself has no hover state.',
      },
    },
  },
}

export const Loading: Story = {
  args: { keys: ['...'], label: 'loading shortcut' },
  parameters: {
    docs: {
      description: {
        story: 'A loading cheatsheet entry renders the ellipsis placeholder until the real shortcut registers.',
      },
    },
  },
}

export const Error: Story = {
  args: { keys: ['!'], label: 'unsupported' },
  parameters: {
    docs: {
      description: {
        story: 'Error content is conveyed via the label -- the component itself has no distinct error surface.',
      },
    },
  },
}

export const Empty: Story = {
  args: { keys: [] },
  parameters: {
    docs: {
      description: {
        story: 'With an empty `keys` array, the component renders just the label (or nothing, if no label). Callers should avoid mounting it when both are empty.',
      },
    },
  },
}
