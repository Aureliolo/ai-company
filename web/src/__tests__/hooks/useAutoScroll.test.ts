import { act, renderHook } from '@testing-library/react'
import { useAutoScroll } from '@/hooks/useAutoScroll'

describe('useAutoScroll', () => {
  function makeContainer(overrides?: Partial<HTMLDivElement>): HTMLDivElement {
    const el = document.createElement('div')
    Object.defineProperty(el, 'scrollHeight', { value: 1000, configurable: true })
    Object.defineProperty(el, 'clientHeight', { value: 400, configurable: true })
    Object.defineProperty(el, 'scrollTop', { value: 600, writable: true, configurable: true })
    if (overrides) {
      for (const [key, value] of Object.entries(overrides)) {
        Object.defineProperty(el, key, { value, writable: true, configurable: true })
      }
    }
    return el
  }

  it('returns isAutoScrolling true by default', () => {
    const { result } = renderHook(() => useAutoScroll())
    expect(result.current.isAutoScrolling).toBe(true)
  })

  it('scrollToBottom scrolls the container to the bottom', () => {
    const container = makeContainer()
    const ref = { current: container }
    const { result } = renderHook(() => useAutoScroll(ref))

    result.current.scrollToBottom()
    expect(container.scrollTop).toBe(container.scrollHeight)
  })

  it('returns isAutoScrolling false when user scrolls away from bottom', () => {
    const container = makeContainer({ scrollTop: 100 })
    const ref = { current: container }
    const { result } = renderHook(() => useAutoScroll(ref))

    // Simulate scroll event inside act to process state update
    act(() => {
      container.dispatchEvent(new Event('scroll'))
    })

    // User is at scrollTop=100, far from bottom (scrollHeight=1000, clientHeight=400)
    // Bottom would be at 600. Threshold default is 50px.
    expect(result.current.isAutoScrolling).toBe(false)
  })

  it('returns isAutoScrolling true when user scrolls near bottom', () => {
    // Near bottom: scrollTop >= scrollHeight - clientHeight - threshold
    // 560 >= 1000 - 400 - 50 = 550 -> true
    const container = makeContainer({ scrollTop: 560 })
    const ref = { current: container }
    const { result } = renderHook(() => useAutoScroll(ref))

    act(() => {
      container.dispatchEvent(new Event('scroll'))
    })

    expect(result.current.isAutoScrolling).toBe(true)
  })

  it('scrollToBottom re-enables auto-scrolling after user scrolled away', () => {
    const container = makeContainer({ scrollTop: 100 })
    const ref = { current: container }
    const { result } = renderHook(() => useAutoScroll(ref))

    // User scrolls away
    act(() => {
      container.dispatchEvent(new Event('scroll'))
    })
    expect(result.current.isAutoScrolling).toBe(false)

    // scrollToBottom re-enables auto-scrolling
    act(() => {
      result.current.scrollToBottom()
    })
    expect(result.current.isAutoScrolling).toBe(true)
    expect(container.scrollTop).toBe(container.scrollHeight)
  })

  it('handles null ref gracefully', () => {
    const ref = { current: null }
    const { result } = renderHook(() => useAutoScroll(ref))

    expect(result.current.isAutoScrolling).toBe(true)
    // Should not throw
    result.current.scrollToBottom()
  })
})
