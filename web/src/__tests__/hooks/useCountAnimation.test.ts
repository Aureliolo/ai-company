import { act, renderHook } from '@testing-library/react'
import { useCountAnimation } from '@/hooks/useCountAnimation'

describe('useCountAnimation', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Mock requestAnimationFrame with proper handle mapping for cancelAnimationFrame
    const timeoutMap = new Map<number, ReturnType<typeof setTimeout>>()
    let rafId = 0
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      rafId += 1
      const id = rafId
      const timeoutId = setTimeout(() => {
        timeoutMap.delete(id)
        cb(performance.now())
      }, 16)
      timeoutMap.set(id, timeoutId)
      return id
    })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => {
      const timeoutId = timeoutMap.get(id)
      if (timeoutId !== undefined) {
        clearTimeout(timeoutId)
        timeoutMap.delete(id)
      }
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('returns the target value immediately on first render', () => {
    const { result } = renderHook(() => useCountAnimation(42))
    expect(result.current).toBe(42)
  })

  it('returns the target value immediately when reduced motion is preferred', () => {
    // jsdom does not define matchMedia, so stub it globally
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    }))

    const { result, rerender } = renderHook(
      ({ value }) => useCountAnimation(value),
      { initialProps: { value: 0 } },
    )

    rerender({ value: 100 })
    // Should immediately show 100 without animation
    expect(result.current).toBe(100)
  })

  it('animates from old value toward new value', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useCountAnimation(value, { durationMs: 200 }),
      { initialProps: { value: 0 } },
    )

    expect(result.current).toBe(0)

    rerender({ value: 100 })

    // Advance partially through animation
    act(() => {
      vi.advanceTimersByTime(100)
    })

    // Value should be strictly between 0 and 100 (mid-animation, not yet at target)
    expect(result.current).toBeGreaterThan(0)
    expect(result.current).toBeLessThan(100)
  })

  it('reaches the target value after full duration', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useCountAnimation(value, { durationMs: 200 }),
      { initialProps: { value: 0 } },
    )

    rerender({ value: 100 })

    // Advance past the full duration
    act(() => {
      vi.advanceTimersByTime(300)
    })

    expect(result.current).toBe(100)
  })

  it('returns a numeric value', () => {
    const { result } = renderHook(() => useCountAnimation(42))
    expect(typeof result.current).toBe('number')
  })
})
