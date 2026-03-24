import { renderHook, act } from '@testing-library/react'
import { AxiosError, type AxiosResponse } from 'axios'
import { useLoginLockout } from '@/hooks/useLoginLockout'
import { LOGIN_MAX_ATTEMPTS, LOGIN_LOCKOUT_MS } from '@/utils/constants'

function make4xxError(status = 401): AxiosError {
  return new AxiosError(
    'Request failed',
    'ERR_BAD_RESPONSE',
    undefined,
    undefined,
    { status, data: {}, headers: {}, statusText: 'Error', config: {} as AxiosResponse['config'] } as AxiosResponse,
  )
}

function make5xxError(): AxiosError {
  return new AxiosError(
    'Request failed',
    'ERR_BAD_RESPONSE',
    undefined,
    undefined,
    { status: 500, data: {}, headers: {}, statusText: 'Error', config: {} as AxiosResponse['config'] } as AxiosResponse,
  )
}

describe('useLoginLockout', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts unlocked', () => {
    const { result } = renderHook(() => useLoginLockout())
    expect(result.current.locked).toBe(false)
  })

  it('does not count 5xx errors toward lockout', () => {
    const { result } = renderHook(() => useLoginLockout())

    for (let i = 0; i < LOGIN_MAX_ATTEMPTS + 5; i++) {
      act(() => {
        result.current.recordFailure(make5xxError())
      })
    }

    expect(result.current.locked).toBe(false)
  })

  it('does not count non-axios errors toward lockout', () => {
    const { result } = renderHook(() => useLoginLockout())

    for (let i = 0; i < LOGIN_MAX_ATTEMPTS + 5; i++) {
      act(() => {
        result.current.recordFailure(new Error('network error'))
      })
    }

    expect(result.current.locked).toBe(false)
  })

  it('locks after LOGIN_MAX_ATTEMPTS 4xx failures', () => {
    const { result } = renderHook(() => useLoginLockout())

    let lockoutMsg: string | null = null
    for (let i = 0; i < LOGIN_MAX_ATTEMPTS; i++) {
      act(() => {
        lockoutMsg = result.current.recordFailure(make4xxError())
      })
    }

    expect(lockoutMsg).toContain('Too many failed attempts')
    expect(result.current.locked).toBe(true)
  })

  it('unlocks after lockout period expires', () => {
    const { result } = renderHook(() => useLoginLockout())

    // Trigger lockout
    for (let i = 0; i < LOGIN_MAX_ATTEMPTS; i++) {
      act(() => {
        result.current.recordFailure(make4xxError())
      })
    }
    expect(result.current.locked).toBe(true)

    // Advance past lockout
    act(() => {
      vi.advanceTimersByTime(LOGIN_LOCKOUT_MS + 1000)
    })

    expect(result.current.locked).toBe(false)
  })

  it('resets on successful auth', () => {
    const { result } = renderHook(() => useLoginLockout())

    // Accumulate some failures
    for (let i = 0; i < LOGIN_MAX_ATTEMPTS - 1; i++) {
      act(() => {
        result.current.recordFailure(make4xxError())
      })
    }

    act(() => {
      result.current.reset()
    })

    // One more failure should not trigger lockout (counter was reset)
    act(() => {
      result.current.recordFailure(make4xxError())
    })

    expect(result.current.locked).toBe(false)
  })

  it('checkAndClearLockout clears expired lockout', () => {
    const { result } = renderHook(() => useLoginLockout())

    // Trigger lockout
    for (let i = 0; i < LOGIN_MAX_ATTEMPTS; i++) {
      act(() => {
        result.current.recordFailure(make4xxError())
      })
    }

    // Advance past lockout
    act(() => {
      vi.advanceTimersByTime(LOGIN_LOCKOUT_MS + 1000)
    })

    let stillLocked: boolean = true
    act(() => {
      stillLocked = result.current.checkAndClearLockout()
    })

    expect(stillLocked).toBe(false)
  })
})
