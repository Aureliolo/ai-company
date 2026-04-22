import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CommandCheatsheet } from '@/components/ui/command-cheatsheet'
import { ShortcutRegistryProvider } from '@/components/shortcut-registry-provider'
import { useRegisterShortcuts } from '@/hooks/use-shortcut-registry'

function Harness({ children, open }: { children?: React.ReactNode; open?: boolean }) {
  return (
    <ShortcutRegistryProvider>
      {children}
      <CommandCheatsheet open={open} />
    </ShortcutRegistryProvider>
  )
}

function SeedShortcuts() {
  useRegisterShortcuts([
    { keys: ['Ctrl', 'K'], label: 'Palette', group: 'Global' },
    { keys: ['j'], label: 'Next', group: 'List' },
  ])
  return null
}

describe('CommandCheatsheet', () => {
  it('renders registered shortcuts grouped by group', () => {
    render(
      <Harness open>
        <SeedShortcuts />
      </Harness>,
    )
    expect(screen.getByText('Global')).toBeInTheDocument()
    expect(screen.getByText('List')).toBeInTheDocument()
    expect(screen.getByText('Palette')).toBeInTheDocument()
    expect(screen.getByText('Next')).toBeInTheDocument()
  })

  it('shows empty state when no shortcuts registered', () => {
    render(<Harness open />)
    expect(screen.getByText(/No shortcuts registered/)).toBeInTheDocument()
  })

  it('has a Close button', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    render(
      <ShortcutRegistryProvider>
        <CommandCheatsheet open onOpenChange={onOpenChange} />
      </ShortcutRegistryProvider>,
    )
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('? shortcut toggles open state in uncontrolled mode', () => {
    render(
      <ShortcutRegistryProvider>
        <CommandCheatsheet />
      </ShortcutRegistryProvider>,
    )
    // Initially closed -- dialog popup not visible
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    act(() => {
      fireEvent.keyDown(window, { key: '?' })
    })
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('? shortcut is ignored when focus is inside input', () => {
    render(
      <ShortcutRegistryProvider>
        <input aria-label="field" />
        <CommandCheatsheet />
      </ShortcutRegistryProvider>,
    )
    const input = screen.getByLabelText('field')
    input.focus()
    act(() => {
      fireEvent.keyDown(window, { key: '?' })
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('disableShortcut prop disables the ? toggle', () => {
    render(
      <ShortcutRegistryProvider>
        <CommandCheatsheet disableShortcut />
      </ShortcutRegistryProvider>,
    )
    act(() => {
      fireEvent.keyDown(window, { key: '?' })
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
