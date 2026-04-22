import type { Meta, StoryObj } from '@storybook/react'
import { ShortcutRegistryProvider } from '@/components/shortcut-registry-provider'
import { useRegisterShortcuts } from '@/hooks/use-shortcut-registry'
import { CommandCheatsheet } from './command-cheatsheet'

function SeedGlobalShortcuts() {
  useRegisterShortcuts([
    { keys: ['Ctrl', 'K'], label: 'Open command palette', group: 'Global' },
    { keys: ['?'], label: 'Toggle this cheatsheet', group: 'Global' },
    { keys: ['g', 'a'], label: 'Go to Agents', group: 'Global' },
    { keys: ['g', 't'], label: 'Go to Tasks', group: 'Global' },
    { keys: ['g', 'd'], label: 'Go to Dashboard', group: 'Global' },
  ])
  return null
}

function SeedListShortcuts() {
  useRegisterShortcuts([
    { keys: ['j'], label: 'Next item', group: 'List' },
    { keys: ['k'], label: 'Previous item', group: 'List' },
    { keys: ['Enter'], label: 'Open selected', group: 'List' },
    { keys: ['e'], label: 'Edit selected', group: 'List' },
    { keys: ['Del'], label: 'Delete selected (confirms)', group: 'List' },
    { keys: ['/'], label: 'Focus search', group: 'List' },
  ])
  return null
}

const meta = {
  title: 'Overlays/CommandCheatsheet',
  component: CommandCheatsheet,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <ShortcutRegistryProvider>
        <SeedGlobalShortcuts />
        <SeedListShortcuts />
        <Story />
      </ShortcutRegistryProvider>
    ),
  ],
  parameters: { layout: 'centered' },
} satisfies Meta<typeof CommandCheatsheet>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {
  args: { open: true },
}

export const Closed: Story = {
  args: { open: false },
}

function NoShortcutsDemo() {
  // Override -- no shortcuts registered in this scope
  return (
    <ShortcutRegistryProvider>
      <CommandCheatsheet open />
    </ShortcutRegistryProvider>
  )
}

export const NoShortcuts: Story = {
  args: { open: true },
  render: () => <NoShortcutsDemo />,
}

function ToggleDemo() {
  return (
    <>
      <p className="mb-4 text-xs text-muted-foreground">
        Press <kbd className="rounded border border-border bg-surface px-1 py-0.5 text-[10px]">?</kbd> to toggle the cheatsheet.
      </p>
      <CommandCheatsheet />
    </>
  )
}

export const Toggle: Story = {
  args: {},
  render: () => <ToggleDemo />,
}
