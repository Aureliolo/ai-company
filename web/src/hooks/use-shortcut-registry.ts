import { createContext, use, useEffect, useId } from 'react'

export interface RegisteredShortcut {
  /** Keys pressed in sequence, rendered as `<kbd>` pills. Example: `['Ctrl', 'K']`. */
  keys: string[]
  /** Human-readable action description. */
  label: string
  /** Logical grouping used by `<CommandCheatsheet>`. Pages should supply a consistent group name. */
  group: string
}

export interface ShortcutRegistryContextValue {
  shortcuts: ReadonlyArray<{ id: string } & RegisteredShortcut>
  register: (id: string, shortcuts: RegisteredShortcut[]) => void
  unregister: (id: string) => void
}

export const ShortcutRegistryContext = createContext<ShortcutRegistryContextValue | null>(null)

export function useShortcutRegistry() {
  const ctx = use(ShortcutRegistryContext)
  if (!ctx) {
    throw new Error('useShortcutRegistry must be used inside <ShortcutRegistryProvider>')
  }
  return ctx
}

/**
 * Register a set of shortcuts while this component is mounted. Shortcuts
 * are exposed via `useShortcutRegistry().shortcuts` for `<CommandCheatsheet>`
 * to display. This hook does NOT attach any keyboard handlers -- registration
 * is documentation/display-only. Handlers are wired separately (via
 * `useListShortcuts`, `useCommandPalette`, etc.).
 */
export function useRegisterShortcuts(shortcuts: RegisteredShortcut[]) {
  const ctx = use(ShortcutRegistryContext)
  const ownerId = useId()
  useEffect(() => {
    if (!ctx) return
    ctx.register(ownerId, shortcuts)
    return () => ctx.unregister(ownerId)
    // Shortcuts array identity change forces re-registration; consumers
    // should memoize via useMemo if they construct shortcuts inline.
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [ctx, ownerId, JSON.stringify(shortcuts)])
}
