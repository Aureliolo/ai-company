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
  // Destructure the stable callbacks so the effect does not re-run every
  // time the context value object identity changes. Depending on `ctx`
  // directly would create an infinite loop: register -> provider re-renders
  // -> ctx identity changes -> effect re-runs -> register again -> ...
  const register = ctx?.register
  const unregister = ctx?.unregister
  const ownerId = useId()
  useEffect(() => {
    if (!register || !unregister) return
    register(ownerId, shortcuts)
    return () => unregister(ownerId)
    // Shortcuts array identity change forces re-registration; consumers
    // should memoize via useMemo if they construct shortcuts inline. We
    // keep JSON.stringify for content-based change detection so an
    // unmemoized array of the same content does not thrash the registry.
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [register, unregister, ownerId, JSON.stringify(shortcuts)])
}
