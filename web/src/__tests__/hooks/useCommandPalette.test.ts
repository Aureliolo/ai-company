import { act, renderHook } from '@testing-library/react'
import type { CommandItem } from '@/hooks/useCommandPalette'
import {
  _reset,
  useCommandPalette,
} from '@/hooks/useCommandPalette'

function makeCommand(overrides: Partial<CommandItem> = {}): CommandItem {
  return {
    id: `test-${Math.random().toString(36).slice(2)}`,
    label: 'Test Command',
    action: vi.fn(),
    group: 'Test',
    ...overrides,
  }
}

describe('useCommandPalette', () => {
  beforeEach(() => {
    _reset()
  })

  it('starts with empty commands', () => {
    const { result } = renderHook(() => useCommandPalette())
    expect(result.current.commands).toHaveLength(0)
  })

  it('starts closed', () => {
    const { result } = renderHook(() => useCommandPalette())
    expect(result.current.isOpen).toBe(false)
  })

  it('registerCommands adds commands to the list', () => {
    const { result } = renderHook(() => useCommandPalette())

    act(() => {
      result.current.registerCommands([makeCommand()])
    })

    expect(result.current.commands).toHaveLength(1)
    expect(result.current.commands[0]?.label).toBe('Test Command')
  })

  it('cleanup function removes commands', () => {
    const { result } = renderHook(() => useCommandPalette())

    let cleanup: () => void
    act(() => {
      cleanup = result.current.registerCommands([makeCommand()])
    })
    expect(result.current.commands).toHaveLength(1)

    act(() => {
      cleanup()
    })
    expect(result.current.commands).toHaveLength(0)
  })

  it('multiple registrations merge', () => {
    const { result } = renderHook(() => useCommandPalette())

    act(() => {
      result.current.registerCommands([makeCommand({ id: 'a', label: 'A' })])
      result.current.registerCommands([makeCommand({ id: 'b', label: 'B' })])
    })

    expect(result.current.commands).toHaveLength(2)
  })

  it('open() sets isOpen to true', () => {
    const { result } = renderHook(() => useCommandPalette())

    act(() => {
      result.current.open()
    })
    expect(result.current.isOpen).toBe(true)
  })

  it('close() sets isOpen to false', () => {
    const { result } = renderHook(() => useCommandPalette())

    act(() => {
      result.current.open()
    })
    expect(result.current.isOpen).toBe(true)

    act(() => {
      result.current.close()
    })
    expect(result.current.isOpen).toBe(false)
  })

  it('toggle() flips isOpen', () => {
    const { result } = renderHook(() => useCommandPalette())

    act(() => {
      result.current.toggle()
    })
    expect(result.current.isOpen).toBe(true)

    act(() => {
      result.current.toggle()
    })
    expect(result.current.isOpen).toBe(false)
  })
})
