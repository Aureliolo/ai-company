import { renderHook, act } from '@testing-library/react'
import { useRovingTabIndex } from '@/hooks/useRovingTabIndex'

function makeContainer(itemCount: number): HTMLDivElement {
  const container = document.createElement('div')
  for (let i = 0; i < itemCount; i++) {
    const item = document.createElement('button')
    item.setAttribute('data-roving-item', '')
    item.textContent = `Item ${i}`
    container.appendChild(item)
  }
  document.body.appendChild(container)
  return container
}

describe('useRovingTabIndex', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('sets first item to tabIndex 0 and rest to -1', () => {
    const container = makeContainer(3)
    const ref = { current: container }

    renderHook(() => useRovingTabIndex({ containerRef: ref, orientation: 'vertical' }))

    const items = container.querySelectorAll('[data-roving-item]')
    expect(items[0]!.getAttribute('tabindex')).toBe('0')
    expect(items[1]!.getAttribute('tabindex')).toBe('-1')
    expect(items[2]!.getAttribute('tabindex')).toBe('-1')
  })

  it('moves focus down on ArrowDown in vertical mode', () => {
    const container = makeContainer(3)
    const ref = { current: container }

    const { result } = renderHook(() =>
      useRovingTabIndex({ containerRef: ref, orientation: 'vertical' }),
    )

    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowDown' }))
    })

    expect(result.current.focusedIndex).toBe(1)
  })

  it('moves focus up on ArrowUp in vertical mode', () => {
    const container = makeContainer(3)
    const ref = { current: container }

    const { result } = renderHook(() =>
      useRovingTabIndex({ containerRef: ref, orientation: 'vertical' }),
    )

    // Move to index 2 first (one step at a time so state flushes)
    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowDown' }))
    })
    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowDown' }))
    })
    expect(result.current.focusedIndex).toBe(2)

    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowUp' }))
    })
    expect(result.current.focusedIndex).toBe(1)
  })

  it('moves focus with ArrowLeft/Right in horizontal mode', () => {
    const container = makeContainer(3)
    const ref = { current: container }

    const { result } = renderHook(() =>
      useRovingTabIndex({ containerRef: ref, orientation: 'horizontal' }),
    )

    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    })
    expect(result.current.focusedIndex).toBe(1)

    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowLeft' }))
    })
    expect(result.current.focusedIndex).toBe(0)
  })

  it('Home jumps to first item, End to last', () => {
    const container = makeContainer(5)
    const ref = { current: container }

    const { result } = renderHook(() =>
      useRovingTabIndex({ containerRef: ref, orientation: 'vertical' }),
    )

    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'End' }))
    })
    expect(result.current.focusedIndex).toBe(4)

    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'Home' }))
    })
    expect(result.current.focusedIndex).toBe(0)
  })

  it('wraps around with loop enabled', () => {
    const container = makeContainer(3)
    const ref = { current: container }

    const { result } = renderHook(() =>
      useRovingTabIndex({ containerRef: ref, orientation: 'vertical', loop: true }),
    )

    // At index 0, ArrowUp should wrap to last
    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowUp' }))
    })
    expect(result.current.focusedIndex).toBe(2)
  })

  it('does not wrap without loop', () => {
    const container = makeContainer(3)
    const ref = { current: container }

    const { result } = renderHook(() =>
      useRovingTabIndex({ containerRef: ref, orientation: 'vertical', loop: false }),
    )

    // At index 0, ArrowUp should stay at 0
    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowUp' }))
    })
    expect(result.current.focusedIndex).toBe(0)
  })

  it('navigates grid with columns in grid mode', () => {
    const container = makeContainer(6)
    const ref = { current: container }

    const { result } = renderHook(() =>
      useRovingTabIndex({ containerRef: ref, orientation: 'grid', columns: 3 }),
    )

    // ArrowRight moves horizontal
    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    })
    expect(result.current.focusedIndex).toBe(1)

    // ArrowDown moves by columns (3)
    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowDown' }))
    })
    expect(result.current.focusedIndex).toBe(4)
  })

  it('handles null container ref gracefully', () => {
    const ref = { current: null }
    const { result } = renderHook(() =>
      useRovingTabIndex({ containerRef: ref, orientation: 'vertical' }),
    )

    expect(result.current.focusedIndex).toBe(0)
    // Should not throw
    act(() => {
      result.current.handleKeyDown(new KeyboardEvent('keydown', { key: 'ArrowDown' }))
    })
  })
})
