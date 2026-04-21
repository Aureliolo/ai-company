import type { Meta, StoryObj } from '@storybook/react'
import { KeyboardShortcutHint } from './keyboard-shortcut-hint'

const meta = {
  title: 'Overlays/KeyboardShortcutHint',
  component: KeyboardShortcutHint,
  tags: ['autodocs'],
  parameters: { layout: 'padded' },
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
