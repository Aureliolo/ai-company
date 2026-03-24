import { useCallback, useEffect, useRef, useState } from 'react'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'

const MIN_POLL_INTERVAL = 100

/**
 * Poll a function at a fixed interval with cleanup on unmount.
 * Uses setTimeout-based scheduling to prevent overlapping async calls.
 * A run generation counter prevents stale in-flight runs from spawning
 * duplicate loops after stop/start cycles.
 */
export function usePolling(fn: () => Promise<void>, intervalMs: number): {
  active: boolean
  error: string | null
  start: () => void
  stop: () => void
} {
  const [active, setActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const activeRef = useRef(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fnRef = useRef(fn)
  const runIdRef = useRef(0)
  fnRef.current = fn

  // Validate at start, not during render
  const isValidInterval = Number.isFinite(intervalMs) && intervalMs >= MIN_POLL_INTERVAL

  const scheduleTick = useCallback((runId: number) => {
    if (!activeRef.current || runId !== runIdRef.current) return
    timerRef.current = setTimeout(async () => {
      if (!activeRef.current || runId !== runIdRef.current) return
      try {
        await fnRef.current()
        setError(null)
      } catch (err) {
        setError(getErrorMessage(err))
        console.error('Polling error:', sanitizeForLog(err))
      }
      scheduleTick(runId)
    }, intervalMs)
  }, [intervalMs])

  const start = useCallback(() => {
    if (!isValidInterval) {
      console.error(`usePolling: intervalMs must be a finite number >= ${MIN_POLL_INTERVAL}, got ${intervalMs}`)
      return
    }
    if (activeRef.current) return
    activeRef.current = true
    setActive(true)
    setError(null)
    const runId = ++runIdRef.current
    const immediate = async () => {
      if (!activeRef.current || runId !== runIdRef.current) return
      try {
        await fnRef.current()
      } catch (err) {
        setError(getErrorMessage(err))
        console.error('Polling error:', sanitizeForLog(err))
      }
      scheduleTick(runId)
    }
    immediate().catch((err) => {
      console.error('Polling initial run failed:', sanitizeForLog(err))
    })
  }, [scheduleTick, isValidInterval, intervalMs])

  const stop = useCallback(() => {
    activeRef.current = false
    setActive(false)
    runIdRef.current++
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop()
    }
  }, [stop])

  return { active, error, start, stop }
}
