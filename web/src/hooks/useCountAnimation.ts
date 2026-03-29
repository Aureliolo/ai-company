import { useEffect, useRef, useState } from 'react'

const DEFAULT_DURATION_MS = 200

interface UseCountAnimationOptions {
  /** Animation duration in ms. Default: 200. */
  durationMs?: number
}

/**
 * Animate a numeric value transition using requestAnimationFrame.
 *
 * On first render, returns the target immediately (no animation).
 * On subsequent value changes, animates from the previous value to the new one.
 * Respects `prefers-reduced-motion` (returns target instantly).
 */
export function useCountAnimation(
  target: number,
  options?: UseCountAnimationOptions,
): number {
  const durationMs = options?.durationMs ?? DEFAULT_DURATION_MS
  const [display, setDisplay] = useState(target)
  const previousValueRef = useRef(target)
  const firstRenderRef = useRef(true)
  const animationFrameRef = useRef<number | null>(null)

  useEffect(() => {
    // On first render, just set the value -- no animation needed
    if (firstRenderRef.current) {
      firstRenderRef.current = false
      previousValueRef.current = target
      return
    }

    // Check reduced motion preference
    if (
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      previousValueRef.current = target
      setDisplay(target) // eslint-disable-line @eslint-react/set-state-in-effect -- reduced-motion early return
      return
    }

    const from = previousValueRef.current
    const delta = target - from
    previousValueRef.current = target

    // No change -- skip animation
    if (delta === 0) return

    const startTime = performance.now()

    function animate(now: number) {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / durationMs, 1)
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = from + delta * eased

      setDisplay(Math.round(current))

      if (progress < 1) {
        animationFrameRef.current = requestAnimationFrame(animate)
      }
    }

    animationFrameRef.current = requestAnimationFrame(animate)

    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [target, durationMs])

  return display
}
