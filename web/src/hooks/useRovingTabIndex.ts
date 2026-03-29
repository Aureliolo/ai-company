import { useCallback, useEffect, useState } from 'react'
import type { RefObject } from 'react'

interface UseRovingTabIndexOptions {
  containerRef: RefObject<HTMLElement | null>
  orientation: 'vertical' | 'horizontal' | 'grid'
  /** Number of columns for grid orientation. Required when orientation is 'grid'. */
  columns?: number
  /** Whether to wrap focus around at boundaries. Default: true. */
  loop?: boolean
}

interface UseRovingTabIndexReturn {
  /** Index of the currently focused item. */
  focusedIndex: number
  /** Returns 0 for the focused item, -1 for all others. */
  getTabIndex: (index: number) => 0 | -1
  /** Key event handler to attach to the container. */
  handleKeyDown: (event: KeyboardEvent | React.KeyboardEvent) => void
}

const ITEM_SELECTOR = '[data-roving-item]'

/**
 * Roving tabindex pattern for arrow-key navigation through lists and grids.
 *
 * The focused item gets `tabIndex={0}` and all others get `tabIndex={-1}`.
 * Attach `data-roving-item` to each navigable child element.
 */
export function useRovingTabIndex(options: UseRovingTabIndexOptions): UseRovingTabIndexReturn {
  const { containerRef, orientation, columns = 1, loop = true } = options
  const [focusedIndex, setFocusedIndex] = useState(0)

  // Sync tabindex attributes when focused index changes
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const items = container.querySelectorAll<HTMLElement>(ITEM_SELECTOR)
    items.forEach((item, i) => {
      item.setAttribute('tabindex', i === focusedIndex ? '0' : '-1')
    })
  }, [containerRef, focusedIndex])

  const getTabIndex = useCallback(
    (index: number): 0 | -1 => (index === focusedIndex ? 0 : -1),
    [focusedIndex],
  )

  const handleKeyDown = useCallback(
    (event: KeyboardEvent | React.KeyboardEvent) => {
      const container = containerRef.current
      if (!container) return

      const items = container.querySelectorAll<HTMLElement>(ITEM_SELECTOR)
      const count = items.length
      if (count === 0) return

      let nextIndex: number | null = null
      const { key } = event

      if (orientation === 'vertical') {
        if (key === 'ArrowDown') nextIndex = focusedIndex + 1
        else if (key === 'ArrowUp') nextIndex = focusedIndex - 1
      } else if (orientation === 'horizontal') {
        if (key === 'ArrowRight') nextIndex = focusedIndex + 1
        else if (key === 'ArrowLeft') nextIndex = focusedIndex - 1
      } else if (orientation === 'grid') {
        if (key === 'ArrowRight') nextIndex = focusedIndex + 1
        else if (key === 'ArrowLeft') nextIndex = focusedIndex - 1
        else if (key === 'ArrowDown') nextIndex = focusedIndex + columns
        else if (key === 'ArrowUp') nextIndex = focusedIndex - columns
      }

      if (key === 'Home') nextIndex = 0
      else if (key === 'End') nextIndex = count - 1

      if (nextIndex === null) return

      event.preventDefault()

      if (loop) {
        nextIndex = ((nextIndex % count) + count) % count
      } else {
        nextIndex = Math.max(0, Math.min(count - 1, nextIndex))
      }

      setFocusedIndex(nextIndex)
      items[nextIndex]?.focus()
    },
    [containerRef, orientation, columns, loop, focusedIndex],
  )

  return { focusedIndex, getTabIndex, handleKeyDown }
}
