import { useEffect, useRef, useState } from 'react'

export interface UseListShortcutsOptions {
  /** Total number of items in the active list. */
  itemCount: number
  /** Handler when user presses Enter on the selected row. */
  onOpen?: (index: number) => void
  /** Handler when user presses `e` on the selected row (edit). */
  onEdit?: (index: number) => void
  /** Handler when user presses Delete or Backspace on the selected row (destructive). */
  onDelete?: (index: number) => void
  /** Handler for `/` -- focus the list's search input. */
  onFocusSearch?: () => void
  /** Disable all shortcuts (e.g. when a modal is open). */
  disabled?: boolean
}

export interface UseListShortcutsResult {
  selectedIndex: number | null
  setSelectedIndex: (index: number | null) => void
}

function isEditable(el: Element | null): boolean {
  if (!el) return false
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  return (el as HTMLElement).isContentEditable === true
}

/**
 * Keyboard shortcuts for list pages.
 *
 * Registered shortcuts (when no input is focused and `disabled` is false):
 * - `j` / `ArrowDown`: select next item
 * - `k` / `ArrowUp`: select previous item
 * - `g g`: select first item (press `g` twice within 500ms)
 * - `Shift+G`: select last item
 * - `Enter`: invoke `onOpen`
 * - `e`: invoke `onEdit`
 * - `Delete` / `Backspace`: invoke `onDelete`
 * - `/`: invoke `onFocusSearch`
 */
export function useListShortcuts({
  itemCount,
  onOpen,
  onEdit,
  onDelete,
  onFocusSearch,
  disabled = false,
}: UseListShortcutsOptions): UseListShortcutsResult {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const lastGRef = useRef<number>(0)

  // Clamp the selection when the list shrinks (or becomes empty) so we never
  // keep a stale index pointing past the end of the array. We call
  // setSelectedIndex via the functional updater so React coalesces the update
  // when the previous and next values already match.
  useEffect(() => {
    // eslint-disable-next-line @eslint-react/set-state-in-effect -- itemCount-driven reconciliation, not a derived-state anti-pattern
    setSelectedIndex((prev) => {
      if (prev === null) return null
      if (itemCount <= 0) return null
      if (prev >= itemCount) return itemCount - 1
      return prev
    })
  }, [itemCount])

  useEffect(() => {
    if (disabled) return
    const handler = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (isEditable(document.activeElement)) return

      const key = event.key
      switch (key) {
        case 'j':
        case 'ArrowDown':
          if (itemCount === 0) return
          event.preventDefault()
          setSelectedIndex((prev) => {
            if (prev === null) return 0
            return Math.min(itemCount - 1, prev + 1)
          })
          break
        case 'k':
        case 'ArrowUp':
          if (itemCount === 0) return
          event.preventDefault()
          setSelectedIndex((prev) => {
            if (prev === null) return 0
            return Math.max(0, prev - 1)
          })
          break
        case 'g': {
          // Shift+g yields event.key === 'G' (handled below), so the
          // lowercase branch only runs for the `g g` (jump-to-top) sequence.
          const now = Date.now()
          if (now - lastGRef.current < 500) {
            if (itemCount === 0) {
              // No items: clear the two-press window but do not set a
              // phantom selection.
              lastGRef.current = 0
              return
            }
            event.preventDefault()
            setSelectedIndex(0)
            lastGRef.current = 0
          } else {
            lastGRef.current = now
          }
          break
        }
        case 'G':
          if (itemCount === 0) return
          event.preventDefault()
          setSelectedIndex(itemCount - 1)
          break
        case 'Enter':
          if (selectedIndex !== null && onOpen) {
            event.preventDefault()
            onOpen(selectedIndex)
          }
          break
        case 'e':
          if (selectedIndex !== null && onEdit) {
            event.preventDefault()
            onEdit(selectedIndex)
          }
          break
        case 'Delete':
        case 'Backspace':
          if (selectedIndex !== null && onDelete) {
            event.preventDefault()
            onDelete(selectedIndex)
          }
          break
        case '/':
          if (onFocusSearch) {
            event.preventDefault()
            onFocusSearch()
          }
          break
        default:
          break
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [disabled, itemCount, onDelete, onEdit, onFocusSearch, onOpen, selectedIndex])

  return { selectedIndex, setSelectedIndex }
}
