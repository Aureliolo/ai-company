import { act, fireEvent, renderHook } from '@testing-library/react'
import fc from 'fast-check'
import { useListShortcuts } from '@/hooks/use-list-shortcuts'

function pressKey(key: string, init?: KeyboardEventInit) {
  act(() => {
    fireEvent.keyDown(window, { key, ...init })
  })
}

describe('useListShortcuts', () => {
  it('j advances selection', () => {
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 5 }),
    )
    expect(result.current.selectedIndex).toBeNull()
    pressKey('j')
    expect(result.current.selectedIndex).toBe(0)
    pressKey('j')
    expect(result.current.selectedIndex).toBe(1)
  })

  it('k retreats selection', () => {
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 5 }),
    )
    act(() => result.current.setSelectedIndex(2))
    pressKey('k')
    expect(result.current.selectedIndex).toBe(1)
    pressKey('k')
    expect(result.current.selectedIndex).toBe(0)
    pressKey('k')
    expect(result.current.selectedIndex).toBe(0)
  })

  it('j at last index stays at last', () => {
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 3 }),
    )
    act(() => result.current.setSelectedIndex(2))
    pressKey('j')
    expect(result.current.selectedIndex).toBe(2)
  })

  it('Shift+G jumps to last', () => {
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 10 }),
    )
    pressKey('G', { shiftKey: true })
    expect(result.current.selectedIndex).toBe(9)
  })

  it('Enter invokes onOpen with selected index', () => {
    const onOpen = vi.fn()
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 5, onOpen }),
    )
    act(() => result.current.setSelectedIndex(3))
    pressKey('Enter')
    expect(onOpen).toHaveBeenCalledWith(3)
  })

  it('Enter with no selection does nothing', () => {
    const onOpen = vi.fn()
    renderHook(() => useListShortcuts({ itemCount: 5, onOpen }))
    pressKey('Enter')
    expect(onOpen).not.toHaveBeenCalled()
  })

  it('e invokes onEdit', () => {
    const onEdit = vi.fn()
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 5, onEdit }),
    )
    act(() => result.current.setSelectedIndex(1))
    pressKey('e')
    expect(onEdit).toHaveBeenCalledWith(1)
  })

  it('Delete invokes onDelete', () => {
    const onDelete = vi.fn()
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 5, onDelete }),
    )
    act(() => result.current.setSelectedIndex(2))
    pressKey('Delete')
    expect(onDelete).toHaveBeenCalledWith(2)
  })

  it('/ invokes onFocusSearch', () => {
    const onFocusSearch = vi.fn()
    renderHook(() => useListShortcuts({ itemCount: 5, onFocusSearch }))
    pressKey('/')
    expect(onFocusSearch).toHaveBeenCalled()
  })

  it('disabled ignores all shortcuts', () => {
    const onOpen = vi.fn()
    renderHook(() => useListShortcuts({ itemCount: 5, onOpen, disabled: true }))
    pressKey('j')
    pressKey('Enter')
    expect(onOpen).not.toHaveBeenCalled()
  })

  it('shortcuts ignored when input is focused', () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 5 }),
    )
    pressKey('j')
    expect(result.current.selectedIndex).toBeNull()
    input.remove()
  })

  it('modifier keys disable shortcuts', () => {
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 5 }),
    )
    pressKey('j', { metaKey: true })
    expect(result.current.selectedIndex).toBeNull()
  })

  it('empty list: `g g` double-press never sets a phantom selection', () => {
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 0 }),
    )
    pressKey('g')
    pressKey('g')
    expect(result.current.selectedIndex).toBeNull()
  })

  it('empty list: Shift+G is also a no-op', () => {
    const { result } = renderHook(() =>
      useListShortcuts({ itemCount: 0 }),
    )
    pressKey('G', { shiftKey: true })
    expect(result.current.selectedIndex).toBeNull()
  })

  it('itemCount shrinks below selectedIndex: selection clamps', () => {
    const { result, rerender } = renderHook(
      ({ itemCount }: { itemCount: number }) => useListShortcuts({ itemCount }),
      { initialProps: { itemCount: 10 } },
    )
    act(() => result.current.setSelectedIndex(7))
    rerender({ itemCount: 3 })
    expect(result.current.selectedIndex).toBe(2)
  })

  it('itemCount drops to zero: selection clears', () => {
    const { result, rerender } = renderHook(
      ({ itemCount }: { itemCount: number }) => useListShortcuts({ itemCount }),
      { initialProps: { itemCount: 10 } },
    )
    act(() => result.current.setSelectedIndex(4))
    rerender({ itemCount: 0 })
    expect(result.current.selectedIndex).toBeNull()
  })

  it('property: j never advances past itemCount-1', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 20 }),
        fc.integer({ min: 1, max: 40 }),
        (itemCount, presses) => {
          const { result, unmount } = renderHook(() =>
            useListShortcuts({ itemCount }),
          )
          for (let i = 0; i < presses; i++) {
            pressKey('j')
          }
          const sel = result.current.selectedIndex
          expect(sel).not.toBeNull()
          expect(sel!).toBeGreaterThanOrEqual(0)
          expect(sel!).toBeLessThanOrEqual(itemCount - 1)
          unmount()
        },
      ),
      { numRuns: 15 },
    )
  })
})
