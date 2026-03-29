import { useEffect, useRef, useState } from 'react'

interface LiveRegionProps {
  children: React.ReactNode
  /** ARIA politeness level. Default: 'polite'. */
  politeness?: 'polite' | 'assertive'
  /** Debounce delay in ms before content updates are announced. Default: 500 for polite, 0 for assertive. */
  debounceMs?: number
  className?: string
}

/**
 * Debounced ARIA live region wrapper.
 *
 * Prevents rapid WS updates from overwhelming screen readers by
 * delaying content updates. Only the latest content is announced.
 */
export function LiveRegion({
  children,
  politeness = 'polite',
  debounceMs,
  className,
}: LiveRegionProps) {
  const effectiveDelay = debounceMs ?? (politeness === 'assertive' ? 0 : 500)
  const [debouncedChildren, setDebouncedChildren] = useState(children)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (effectiveDelay === 0) {
      setDebouncedChildren(children) // eslint-disable-line @eslint-react/set-state-in-effect -- zero-delay means synchronous passthrough
      return
    }

    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
    }

    timerRef.current = setTimeout(() => {
      setDebouncedChildren(children)
      timerRef.current = null
    }, effectiveDelay)

    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
      }
    }
  }, [children, effectiveDelay])

  return (
    <div aria-live={politeness} aria-atomic="true" className={className}>
      {debouncedChildren}
    </div>
  )
}
