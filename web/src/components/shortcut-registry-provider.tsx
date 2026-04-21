import { useCallback, useMemo, useState, type ReactNode } from 'react'
import {
  ShortcutRegistryContext,
  type RegisteredShortcut,
  type ShortcutRegistryContextValue,
} from '@/hooks/use-shortcut-registry'

/**
 * Provides the shortcut registry used by `<CommandCheatsheet>` and
 * `useRegisterShortcuts`. Mount once near the root of the app.
 */
export function ShortcutRegistryProvider({ children }: { children: ReactNode }) {
  // Map keyed by owner id; flattened for consumers. Preserves registration order.
  const [byOwner, setByOwner] = useState<Map<string, RegisteredShortcut[]>>(() => new Map())

  const register = useCallback((id: string, shortcuts: RegisteredShortcut[]) => {
    setByOwner((prev) => {
      const next = new Map(prev)
      next.set(id, shortcuts)
      return next
    })
  }, [])

  const unregister = useCallback((id: string) => {
    setByOwner((prev) => {
      if (!prev.has(id)) return prev
      const next = new Map(prev)
      next.delete(id)
      return next
    })
  }, [])

  const flatShortcuts = useMemo(() => {
    const out: Array<{ id: string } & RegisteredShortcut> = []
    for (const [ownerId, shortcuts] of byOwner) {
      shortcuts.forEach((s, idx) => {
        out.push({ id: `${ownerId}:${idx}`, ...s })
      })
    }
    return out
  }, [byOwner])

  const value = useMemo<ShortcutRegistryContextValue>(
    () => ({ shortcuts: flatShortcuts, register, unregister }),
    [flatShortcuts, register, unregister],
  )

  return <ShortcutRegistryContext value={value}>{children}</ShortcutRegistryContext>
}
