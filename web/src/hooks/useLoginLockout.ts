import { useCallback, useEffect, useRef, useState } from 'react'
import { isAxiosError } from '@/utils/errors'
import { LOGIN_MAX_ATTEMPTS, LOGIN_LOCKOUT_MS } from '@/utils/constants'

/**
 * Shared client-side lockout logic for Login and Setup pages.
 * This is a UX hint only -- real brute-force protection is server-side.
 */
export function useLoginLockout(): {
  locked: boolean
  checkAndClearLockout: () => boolean
  recordFailure: (err: unknown) => string | null
  reset: () => void
} {
  const [lockedUntil, setLockedUntil] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const attemptsRef = useRef(0)

  // Only tick the clock while locked -- avoids 1 re-render/sec when not locked
  useEffect(() => {
    if (!lockedUntil) return
    const id = setInterval(() => { setNow(Date.now()) }, 1000)
    return () => clearInterval(id)
  }, [lockedUntil])

  const locked = !!(lockedUntil && now < lockedUntil)

  const checkAndClearLockout = useCallback((): boolean => {
    if (lockedUntil && Date.now() >= lockedUntil) {
      setLockedUntil(null)
      attemptsRef.current = 0
      return false
    }
    return !!(lockedUntil && Date.now() < lockedUntil)
  }, [lockedUntil])

  const recordFailure = useCallback((err: unknown): string | null => {
    const isCredentialError = isAxiosError(err) &&
      err.response !== undefined &&
      err.response.status >= 400 &&
      err.response.status < 500

    if (isCredentialError) {
      attemptsRef.current += 1
      if (attemptsRef.current >= LOGIN_MAX_ATTEMPTS) {
        setLockedUntil(Date.now() + LOGIN_LOCKOUT_MS)
        attemptsRef.current = 0
        return `Too many failed attempts. Please wait ${LOGIN_LOCKOUT_MS / 1000} seconds.`
      }
    }
    return null
  }, [])

  const reset = useCallback(() => {
    attemptsRef.current = 0
    setLockedUntil(null)
  }, [])

  return { locked, checkAndClearLockout, recordFailure, reset }
}
