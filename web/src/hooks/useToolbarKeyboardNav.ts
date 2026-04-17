import { useCallback, useRef, type KeyboardEvent, type RefObject } from 'react'

/**
 * ARIA toolbar keyboard navigation.
 *
 * Returns a ref to attach to the container with ``role="toolbar"`` and
 * an ``onKeyDown`` handler that routes arrow keys, ``Home``, and
 * ``End`` to the focusable children of the container so tab does not
 * need to step through every control. Tab continues to move focus to
 * the next focusable element outside the toolbar.
 */
export interface ToolbarKeyboardNav<T extends HTMLElement> {
  ref: RefObject<T | null>
  onKeyDown: (event: KeyboardEvent<T>) => void
}

const FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  '[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

export function useToolbarKeyboardNav<
  T extends HTMLElement = HTMLDivElement,
>(): ToolbarKeyboardNav<T> {
  const ref = useRef<T | null>(null)

  const onKeyDown = useCallback((event: KeyboardEvent<T>) => {
    const container = ref.current
    if (!container) return

    // Preserve browser and assistive-tech shortcuts (Ctrl/Cmd/Alt/Shift
    // chords) -- the toolbar only owns plain arrow/Home/End navigation.
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) {
      return
    }

    // Do not intercept arrow keys inside editable controls -- the
    // native caret/value navigation must take precedence. Home/End
    // inside inputs also matters for text editing and we intentionally
    // leave them to the browser.
    const active = document.activeElement
    if (active instanceof HTMLElement) {
      const editable =
        active.tagName === 'INPUT' ||
        active.tagName === 'TEXTAREA' ||
        active.tagName === 'SELECT' ||
        active.isContentEditable
      if (editable) return
    }

    const items = Array.from(
      container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
    ).filter((el) => !el.hasAttribute('data-toolbar-skip'))
    if (items.length === 0) return

    const activeIndex = items.indexOf(active as HTMLElement)

    let nextIndex: number
    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        // -1 (no active item) starts from the first control; from any
        // live index, wrap forward via the cyclic modulo.
        nextIndex = activeIndex < 0 ? 0 : (activeIndex + 1) % items.length
        break
      case 'ArrowLeft':
      case 'ArrowUp':
        nextIndex =
          activeIndex < 0
            ? items.length - 1
            : (activeIndex - 1 + items.length) % items.length
        break
      case 'Home':
        nextIndex = 0
        break
      case 'End':
        nextIndex = items.length - 1
        break
      default:
        return
    }

    event.preventDefault()
    items[nextIndex]?.focus()
  }, [])

  return { ref, onKeyDown }
}
