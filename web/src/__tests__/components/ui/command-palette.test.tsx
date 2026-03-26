import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { CommandItem } from '@/hooks/useCommandPalette'
import {
  _commandGroups,
  _setOpen,
  _updateCommandsSnapshot,
} from '@/hooks/useCommandPalette'
import { CommandPalette } from '@/components/ui/command-palette'

// cmdk uses ResizeObserver and scrollIntoView which are not in jsdom
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver
Element.prototype.scrollIntoView = vi.fn()

function makeCommand(overrides: Partial<CommandItem> = {}): CommandItem {
  return {
    id: `cmd-${Math.random().toString(36).slice(2)}`,
    label: 'Dashboard',
    action: vi.fn(),
    group: 'Navigation',
    ...overrides,
  }
}

function setupCommands(commands: CommandItem[]) {
  const key = 'test-commands'
  _commandGroups.set(key, commands)
  _updateCommandsSnapshot()
}

describe('CommandPalette', () => {
  beforeEach(() => {
    _commandGroups.clear()
    _updateCommandsSnapshot()
    _setOpen(false)
    localStorage.clear()
  })

  it('is not rendered when closed', () => {
    render(<CommandPalette />)
    expect(screen.queryByText('Search commands...')).not.toBeInTheDocument()
  })

  it('opens on Ctrl+K', async () => {
    const user = userEvent.setup()
    render(<CommandPalette />)

    await user.keyboard('{Control>}k{/Control}')
    expect(screen.getByPlaceholderText('Search commands...')).toBeInTheDocument()
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    _setOpen(true)
    render(<CommandPalette />)

    expect(screen.getByPlaceholderText('Search commands...')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByPlaceholderText('Search commands...')).not.toBeInTheDocument()
  })

  it('closes on Ctrl+K again', async () => {
    const user = userEvent.setup()
    render(<CommandPalette />)

    await user.keyboard('{Control>}k{/Control}')
    expect(screen.getByPlaceholderText('Search commands...')).toBeInTheDocument()

    await user.keyboard('{Control>}k{/Control}')
    expect(screen.queryByPlaceholderText('Search commands...')).not.toBeInTheDocument()
  })

  it('displays registered commands', () => {
    setupCommands([
      makeCommand({ label: 'Dashboard', group: 'Navigation' }),
      makeCommand({ label: 'Settings', group: 'Navigation' }),
    ])
    _setOpen(true)
    render(<CommandPalette />)

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('shows "No results found" for unmatched search', async () => {
    const user = userEvent.setup()
    setupCommands([makeCommand({ label: 'Dashboard' })])
    _setOpen(true)
    render(<CommandPalette />)

    await user.type(screen.getByPlaceholderText('Search commands...'), 'zzzzzzz')
    expect(screen.getByText('No results found.')).toBeInTheDocument()
  })

  it('selecting a command calls its action', async () => {
    const user = userEvent.setup()
    const action = vi.fn()
    setupCommands([makeCommand({ label: 'Dashboard', action })])
    _setOpen(true)
    render(<CommandPalette />)

    await user.click(screen.getByText('Dashboard'))
    expect(action).toHaveBeenCalledTimes(1)
  })
})
