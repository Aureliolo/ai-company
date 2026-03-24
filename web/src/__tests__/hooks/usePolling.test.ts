import { renderHook, act } from '@testing-library/react'
import { usePolling } from '@/hooks/usePolling'

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('throws for invalid interval', () => {
    expect(() => {
      renderHook(() => usePolling(vi.fn(), 50))
    }).toThrow('intervalMs must be a finite number >= 100')
  })

  it('starts inactive', () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() => usePolling(fn, 1000))
    expect(result.current.active).toBe(false)
    expect(fn).not.toHaveBeenCalled()
  })

  it('calls fn immediately on start', async () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() => usePolling(fn, 1000))

    await act(async () => {
      result.current.start()
      await vi.advanceTimersByTimeAsync(0) // flush immediate call
    })

    expect(fn).toHaveBeenCalled()
    expect(result.current.active).toBe(true)
  })

  it('calls fn again after interval', async () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() => usePolling(fn, 1000))

    await act(async () => {
      result.current.start()
      await vi.advanceTimersByTimeAsync(0) // immediate call
    })
    expect(fn).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000) // first interval
    })
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('stops polling on stop()', async () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() => usePolling(fn, 1000))

    await act(async () => {
      result.current.start()
      await vi.advanceTimersByTimeAsync(0)
    })

    act(() => {
      result.current.stop()
    })
    expect(result.current.active).toBe(false)

    const callCount = fn.mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(fn).toHaveBeenCalledTimes(callCount) // no new calls
  })

  it('cleans up on unmount', async () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { result, unmount } = renderHook(() => usePolling(fn, 1000))

    await act(async () => {
      result.current.start()
      await vi.advanceTimersByTimeAsync(0)
    })

    unmount()
    const callCount = fn.mock.calls.length

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(fn).toHaveBeenCalledTimes(callCount)
  })

  it('does not overlap calls when fn is slow', async () => {
    let concurrentCalls = 0
    let maxConcurrent = 0

    const fn = vi.fn(async () => {
      concurrentCalls++
      maxConcurrent = Math.max(maxConcurrent, concurrentCalls)
      await new Promise((r) => setTimeout(r, 2000))
      concurrentCalls--
    })

    const { result } = renderHook(() => usePolling(fn, 500))

    await act(async () => {
      result.current.start()
      await vi.advanceTimersByTimeAsync(5000)
    })

    // setTimeout-based scheduling prevents overlap
    expect(maxConcurrent).toBeLessThanOrEqual(1)
  })

  it('ignores duplicate start calls', async () => {
    const fn = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() => usePolling(fn, 1000))

    await act(async () => {
      result.current.start()
      result.current.start() // duplicate
      await vi.advanceTimersByTimeAsync(0)
    })

    // Only called once from the first start
    expect(fn).toHaveBeenCalledTimes(1)
  })
})
