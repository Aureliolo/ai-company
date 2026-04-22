import { useCallback, useMemo, useState, type ReactNode } from 'react'
import {
  ShortcutRegistryContext,
  type RegisteredShortcut,
  type ShortcutRegistryContextValue,
} from '@/hooks/use-shortcut-registry'

function sameShortcutList(
  a: ReadonlyArray<RegisteredShortcut>,
  b: ReadonlyArray<RegisteredShortcut>,
): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) {
    const left = a[i]!
    const right = b[i]!
    if (left.label !== right.label) return false
    if (left.group !== right.group) return false
    if (left.keys.length !== right.keys.length) return false
    for (let j = 0; j < left.keys.length; j++) {
      if (left.keys[j] !== right.keys[j]) return false
    }
  }
  return true
}

/**
 * Provides the shortcut registry used by `<CommandCheatsheet>` and
 * `useRegisterShortcuts`. Mount once near the root of the app.
 */
export function ShortcutRegistryProvider({ children }: { children: ReactNode }) {
  // Map keyed by owner id; flattened for consumers. Preserves registration order.
  const [byOwner, setByOwner] = useState<Map<string, RegisteredShortcut[]>>(() => new Map())

  const register = useCallback((id: string, shortcuts: RegisteredShortcut[]) => {
    setByOwner((prev) => {
      const existing = prev.get(id)
      if (existing && sameShortcutList(existing, shortcuts)) {
        // Semantically identical (same labels / groups / keys) -- skip the
        // Map copy + state update to keep the context stable. Comparing by
        // content (not reference) is critical: when callers construct the
        // shortcuts array inline without `useMemo`, every render produces
        // fresh object references but the content is unchanged. A
        // reference-only short-circuit would miss that and fall into a
        // register→ctx-change→effect→register loop.
        return prev
      }
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
