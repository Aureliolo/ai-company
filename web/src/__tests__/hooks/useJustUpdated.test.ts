import { act, renderHook } from '@testing-library/react'
import { useJustUpdated } from '@/hooks/useJustUpdated'

describe('useJustUpdated', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns false for unknown IDs', () => {
    const { result } = renderHook(() => useJustUpdated())
    expect(result.current.isJustUpdated('unknown')).toBe(false)
  })

  it('marks an ID as just updated after markUpdated', () => {
    const { result } = renderHook(() => useJustUpdated())

    act(() => {
      result.current.markUpdated('agent-1')
    })

    expect(result.current.isJustUpdated('agent-1')).toBe(true)
  })

  it('returns relative time string for updated IDs', () => {
    const { result } = renderHook(() => useJustUpdated())

    act(() => {
      result.current.markUpdated('task-1')
    })

    expect(result.current.relativeTime('task-1')).toBe('just now')
  })

  it('shows seconds after a few seconds', () => {
    const { result } = renderHook(() => useJustUpdated())

    act(() => {
      result.current.markUpdated('task-1')
    })

    act(() => {
      vi.advanceTimersByTime(5000)
    })

    expect(result.current.relativeTime('task-1')).toBe('5s ago')
  })

  it('clears entry after TTL expires', () => {
    const ttlMs = 10_000
    const { result } = renderHook(() => useJustUpdated({ ttlMs }))

    act(() => {
      result.current.markUpdated('agent-1')
    })
    expect(result.current.isJustUpdated('agent-1')).toBe(true)

    act(() => {
      vi.advanceTimersByTime(ttlMs + 100)
    })
    expect(result.current.isJustUpdated('agent-1')).toBe(false)
  })

  it('uses default TTL of 30s', () => {
    const { result } = renderHook(() => useJustUpdated())

    act(() => {
      result.current.markUpdated('id-1')
    })

    act(() => {
      vi.advanceTimersByTime(29_999)
    })
    expect(result.current.isJustUpdated('id-1')).toBe(true)

    act(() => {
      vi.advanceTimersByTime(2)
    })
    expect(result.current.isJustUpdated('id-1')).toBe(false)
  })

  it('re-marking an ID resets the TTL', () => {
    const ttlMs = 10_000
    const { result } = renderHook(() => useJustUpdated({ ttlMs }))

    act(() => {
      result.current.markUpdated('id-1')
    })

    act(() => {
      vi.advanceTimersByTime(8000)
    })
    expect(result.current.isJustUpdated('id-1')).toBe(true)

    // Re-mark resets the TTL
    act(() => {
      result.current.markUpdated('id-1')
    })

    act(() => {
      vi.advanceTimersByTime(8000)
    })
    // Would have expired at 10s from first mark, but re-mark resets
    expect(result.current.isJustUpdated('id-1')).toBe(true)
  })

  it('tracks multiple IDs independently', () => {
    const { result } = renderHook(() => useJustUpdated({ ttlMs: 10_000 }))

    act(() => {
      result.current.markUpdated('a')
    })

    act(() => {
      vi.advanceTimersByTime(5000)
    })

    act(() => {
      result.current.markUpdated('b')
    })

    act(() => {
      vi.advanceTimersByTime(5100)
    })

    // 'a' has been around for 10.1s -- expired
    expect(result.current.isJustUpdated('a')).toBe(false)
    // 'b' has been around for 5.1s -- still valid
    expect(result.current.isJustUpdated('b')).toBe(true)
  })

  it('returns null relative time for unknown IDs', () => {
    const { result } = renderHook(() => useJustUpdated())
    expect(result.current.relativeTime('unknown')).toBeNull()
  })

  it('clearAll removes all tracked IDs', () => {
    const { result } = renderHook(() => useJustUpdated())

    act(() => {
      result.current.markUpdated('a')
      result.current.markUpdated('b')
    })

    act(() => {
      result.current.clearAll()
    })

    expect(result.current.isJustUpdated('a')).toBe(false)
    expect(result.current.isJustUpdated('b')).toBe(false)
  })
})
