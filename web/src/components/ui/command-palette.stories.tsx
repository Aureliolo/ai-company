import type { Meta, StoryObj } from '@storybook/react'
import { useEffect } from 'react'
import {
  Home,
  LayoutGrid,
  Settings,
  Users,
  Wallet,
  CheckSquare,
  MessageSquare,
} from 'lucide-react'
import type { CommandItem } from '@/hooks/useCommandPalette'
import { _setOpen, useCommandPalette } from '@/hooks/useCommandPalette'
import { CommandPalette } from './command-palette'

const sampleCommands: CommandItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: Home, action: () => {}, group: 'Navigation' },
  { id: 'agents', label: 'Agents', icon: Users, action: () => {}, group: 'Navigation' },
  { id: 'tasks', label: 'Task Board', icon: CheckSquare, action: () => {}, group: 'Navigation' },
  { id: 'budget', label: 'Budget', icon: Wallet, action: () => {}, group: 'Navigation' },
  { id: 'messages', label: 'Messages', icon: MessageSquare, action: () => {}, group: 'Navigation' },
  { id: 'settings', label: 'Settings', icon: Settings, action: () => {}, group: 'Navigation', shortcut: ['ctrl', 's'] },
  { id: 'org', label: 'Org Chart', icon: LayoutGrid, action: () => {}, group: 'Navigation' },
]

function PaletteSetup({ commands, open }: { commands: CommandItem[]; open?: boolean }) {
  const { registerCommands } = useCommandPalette()
  useEffect(() => {
    const cleanup = registerCommands(commands)
    _setOpen(open ?? false)
    return () => {
      cleanup()
      _setOpen(false)
    }
  }, [commands, open, registerCommands])
  return <CommandPalette />
}

const meta = {
  title: 'Navigation/CommandPalette',
  component: CommandPalette,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
  },
} satisfies Meta<typeof CommandPalette>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => <PaletteSetup commands={sampleCommands} open />,
}

export const EmptyResults: Story = {
  render: () => <PaletteSetup commands={[]} open />,
}

export const WithPageCommands: Story = {
  render: () => (
    <PaletteSetup
      commands={[
        ...sampleCommands,
        {
          id: 'local-1',
          label: 'Create Agent',
          action: () => {},
          group: 'Page Actions',
          scope: 'local',
        },
        {
          id: 'local-2',
          label: 'Import Agents',
          action: () => {},
          group: 'Page Actions',
          scope: 'local',
        },
      ]}
      open
    />
  ),
}

export const Interactive: Story = {
  render: () => (
    <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
      <PaletteSetup commands={sampleCommands} />
      <p>Press Ctrl+K to open the command palette</p>
    </div>
  ),
}
