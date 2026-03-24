import { useCallback, useEffect, useRef, useState } from 'react'
import { sanitizeForLog } from '@/utils/logging'

const MIN_POLL_INTERVAL = 100

/**
 * Poll a function at a fixed interval with cleanup on unmount.
 * Uses setTimeout-based scheduling to prevent overlapping async calls.
 */
export function usePolling(fn: () => Promise<void>, intervalMs: number): {
  active: boolean
  start: () => void
  stop: () => void
} {
  if (!Number.isFinite(intervalMs) || intervalMs < MIN_POLL_INTERVAL) {
    throw new Error(`usePolling: intervalMs must be a finite number >= ${MIN_POLL_INTERVAL}, got ${intervalMs}`)
  }

  const [active, setActive] = useState(false)
  const activeRef = useRef(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const scheduleTick = useCallback(() => {
    if (!activeRef.current) return
    timerRef.current = setTimeout(async () => {
      if (!activeRef.current) return
      try {
        await fnRef.current()
      } catch (err) {
        console.error('Polling error:', sanitizeForLog(err))
      }
      scheduleTick()
    }, intervalMs)
  }, [intervalMs])

  const start = useCallback(() => {
    if (activeRef.current) return
    activeRef.current = true
    setActive(true)
    const immediate = async () => {
      if (!activeRef.current) return
      try {
        await fnRef.current()
      } catch (err) {
        console.error('Polling error:', sanitizeForLog(err))
      }
      scheduleTick()
    }
    immediate()
  }, [scheduleTick])

  const stop = useCallback(() => {
    activeRef.current = false
    setActive(false)
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      activeRef.current = false
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [])

  return { active, start, stop }
}
