import { useEffect } from 'react'

export interface UseSettingsKeyboardOptions {
  onSave: () => void
  onSearchFocus: () => void
  canSave: boolean
}

export function useSettingsKeyboard({
  onSave,
  onSearchFocus,
  canSave,
}: UseSettingsKeyboardOptions): void {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey
      if (!mod) return

      if (e.key.toLowerCase() === 's') {
        e.preventDefault()
        if (canSave) onSave()
      } else if (e.key === '/') {
        e.preventDefault()
        onSearchFocus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onSave, onSearchFocus, canSave])
}
