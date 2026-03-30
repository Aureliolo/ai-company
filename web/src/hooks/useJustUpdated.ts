import { useCallback, useEffect, useRef, useState } from 'react'

const DEFAULT_TTL_MS = 30_000
const TICK_INTERVAL_MS = 1_000

interface UseJustUpdatedOptions {
  /** Time-to-live in ms before an entry is cleared. Default: 30000. */
  ttlMs?: number
}

interface UseJustUpdatedReturn {
  /** Whether the given ID was updated within the TTL. */
  isJustUpdated: (id: string) => boolean
  /** Relative time string (e.g. "just now", "5s ago") or null if not tracked. */
  relativeTime: (id: string) => string | null
  /** Mark an ID as just updated. Re-marking resets the TTL. */
  markUpdated: (id: string) => void
  /** Clear all tracked IDs. */
  clearAll: () => void
}

function formatRelative(elapsedMs: number): string {
  if (elapsedMs < 2000) return 'just now'
  const seconds = Math.floor(elapsedMs / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ago`
}

/**
 * Track recently-updated entity IDs and provide relative time strings.
 *
 * Entries auto-expire after `ttlMs` (default 30s). The hook ticks every
 * second to keep relative times fresh and garbage-collect expired entries.
 */
export function useJustUpdated(options?: UseJustUpdatedOptions): UseJustUpdatedReturn {
  const rawTtl = options?.ttlMs ?? DEFAULT_TTL_MS
  const ttlMs = Number.isFinite(rawTtl) && rawTtl > 0 ? rawTtl : DEFAULT_TTL_MS
  const entriesRef = useRef(new Map<string, number>())
  // Tick counter drives re-renders every second so relative times update
  const [tick, setTick] = useState(0)
  // Suppress unused variable -- tick forces re-render, read is intentional
  void tick

  // Periodic tick to update relative times and garbage-collect expired entries
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now()
      let changed = false
      for (const [id, timestamp] of entriesRef.current) {
        if (now - timestamp >= ttlMs) {
          entriesRef.current.delete(id)
          changed = true
        }
      }
      // Always tick to update relative times, or if entries were removed
      if (entriesRef.current.size > 0 || changed) {
        setTick((t) => t + 1)
      }
    }, TICK_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [ttlMs])

  const markUpdated = useCallback((id: string) => {
    entriesRef.current.set(id, Date.now())
    setTick((t) => t + 1)
  }, [])

  const isJustUpdated = useCallback((id: string): boolean => {
    const timestamp = entriesRef.current.get(id)
    if (timestamp === undefined) return false
    return Date.now() - timestamp < ttlMs
  }, [ttlMs])

  const relativeTime = useCallback((id: string): string | null => {
    const timestamp = entriesRef.current.get(id)
    if (timestamp === undefined) return null
    // Consistent with isJustUpdated -- return null for expired entries awaiting GC
    if (Date.now() - timestamp >= ttlMs) return null
    return formatRelative(Date.now() - timestamp)
  }, [ttlMs])

  const clearAll = useCallback(() => {
    entriesRef.current.clear()
    setTick((t) => t + 1)
  }, [])

  return { isJustUpdated, relativeTime, markUpdated, clearAll }
}
