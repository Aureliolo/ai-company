import { act, renderHook } from '@testing-library/react'
import { STATUS_FLASH } from '@/lib/motion'
import { useFlash } from '@/hooks/useFlash'

describe('useFlash', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('initial state is not flashing', () => {
    const { result } = renderHook(() => useFlash())
    expect(result.current.flashing).toBe(false)
    expect(result.current.flashClassName).toBe('')
  })

  it('triggerFlash sets flashing to true', () => {
    const { result } = renderHook(() => useFlash())

    act(() => {
      result.current.triggerFlash()
    })

    expect(result.current.flashing).toBe(true)
    expect(result.current.flashClassName).not.toBe('')
  })

  it('flash resets after totalMs', () => {
    const { result } = renderHook(() => useFlash())

    act(() => {
      result.current.triggerFlash()
    })
    expect(result.current.flashing).toBe(true)

    act(() => {
      vi.advanceTimersByTime(STATUS_FLASH.totalMs)
    })
    expect(result.current.flashing).toBe(false)
    expect(result.current.flashClassName).toBe('')
  })

  it('flash does not reset before totalMs', () => {
    const { result } = renderHook(() => useFlash())

    act(() => {
      result.current.triggerFlash()
    })

    act(() => {
      vi.advanceTimersByTime(STATUS_FLASH.totalMs - 1)
    })
    expect(result.current.flashing).toBe(true)
  })

  it('custom durations are respected', () => {
    const customDurations = { flashMs: 100, holdMs: 50, fadeMs: 150 }
    const totalMs = 300
    const { result } = renderHook(() => useFlash(customDurations))

    act(() => {
      result.current.triggerFlash()
    })
    expect(result.current.flashing).toBe(true)

    act(() => {
      vi.advanceTimersByTime(totalMs - 1)
    })
    expect(result.current.flashing).toBe(true)

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(result.current.flashing).toBe(false)
  })

  it('multiple rapid triggers reset the timer (no stacking)', () => {
    const halfway = Math.floor(STATUS_FLASH.totalMs / 2)
    const { result } = renderHook(() => useFlash())

    act(() => {
      result.current.triggerFlash()
    })

    // Advance partway through
    act(() => {
      vi.advanceTimersByTime(halfway)
    })
    expect(result.current.flashing).toBe(true)

    // Trigger again -- should reset the timer
    act(() => {
      result.current.triggerFlash()
    })

    // Advance by the remaining original time -- should still be flashing
    // because the timer was reset
    act(() => {
      vi.advanceTimersByTime(halfway)
    })
    expect(result.current.flashing).toBe(true)

    // Advance the rest of the new timer
    act(() => {
      vi.advanceTimersByTime(STATUS_FLASH.totalMs - halfway)
    })
    expect(result.current.flashing).toBe(false)
  })

  it('flashStyle returns inline style during flash', () => {
    const { result } = renderHook(() => useFlash())

    act(() => {
      result.current.triggerFlash()
    })

    expect(result.current.flashStyle).toHaveProperty('animation')
  })

  it('flashStyle is empty when not flashing', () => {
    const { result } = renderHook(() => useFlash())
    expect(result.current.flashStyle).toEqual({})
  })
})
