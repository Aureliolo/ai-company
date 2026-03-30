import { useCallback, useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

const DEFAULT_THRESHOLD_PX = 50

/**
 * Auto-scroll a container to the bottom when new content arrives,
 * unless the user has scrolled away from the bottom.
 *
 * When the user scrolls back near the bottom (within `thresholdPx`),
 * auto-scrolling resumes.
 */
export function useAutoScroll(
  containerRef?: RefObject<HTMLElement | null>,
  thresholdPx = DEFAULT_THRESHOLD_PX,
): {
  /** Whether auto-scroll is active (user is near the bottom). */
  isAutoScrolling: boolean
  /** Programmatically scroll to the bottom and re-enable auto-scroll. */
  scrollToBottom: () => void
} {
  const [isAutoScrolling, setIsAutoScrolling] = useState(true)
  const isAutoScrollingRef = useRef(true)

  // Track scroll position to determine if user has scrolled away
  useEffect(() => {
    const el = containerRef?.current
    if (!el) return

    function onScroll() {
      const container = containerRef?.current
      if (!container) return
      const nearBottom =
        container.scrollTop >= container.scrollHeight - container.clientHeight - thresholdPx
      if (nearBottom !== isAutoScrollingRef.current) {
        isAutoScrollingRef.current = nearBottom
        setIsAutoScrolling(nearBottom)
      }
    }

    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [containerRef, thresholdPx])

  const scrollToBottom = useCallback(() => {
    const el = containerRef?.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    isAutoScrollingRef.current = true
    setIsAutoScrolling(true)
  }, [containerRef])

  return { isAutoScrolling, scrollToBottom }
}
