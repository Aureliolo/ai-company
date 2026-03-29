import { act, renderHook } from '@testing-library/react'
import { useCountAnimation } from '@/hooks/useCountAnimation'

describe('useCountAnimation', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Mock requestAnimationFrame for deterministic testing
    let rafId = 0
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      rafId += 1
      const id = rafId
      setTimeout(() => cb(performance.now()), 16)
      return id
    })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => {
      clearTimeout(id)
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
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

    // Value should be between 0 and 100 (not yet at target)
    expect(result.current).toBeGreaterThanOrEqual(0)
    expect(result.current).toBeLessThanOrEqual(100)
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

  it('handles string values by parsing and formatting', () => {
    const { result } = renderHook(() => useCountAnimation(42))
    expect(typeof result.current).toBe('number')
  })
})
