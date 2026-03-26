import { useCallback, useEffect, useSyncExternalStore } from 'react'
import type { LucideIcon } from 'lucide-react'

export interface CommandItem {
  id: string
  label: string
  description?: string
  icon?: LucideIcon
  /** Keyboard shortcut display (e.g. ["ctrl", "n"]). */
  shortcut?: string[]
  action: () => void
  /** Group heading in the palette. */
  group: string
  /** Additional search terms. */
  keywords?: string[]
  /** Scope: 'global' (default) or 'local' (page-specific). */
  scope?: 'global' | 'local'
}

// ---------------------------------------------------------------------------
// Module-level store (singleton, shared across all hook instances)
// ---------------------------------------------------------------------------

type RegistrationKey = string

const commandGroups = new Map<RegistrationKey, CommandItem[]>()
const listeners = new Set<() => void>()
let openState = false
let registrationCounter = 0

function emitChange() {
  for (const listener of listeners) {
    listener()
  }
}

function getAllCommands(): CommandItem[] {
  const all: CommandItem[] = []
  for (const group of commandGroups.values()) {
    all.push(...group)
  }
  return all
}

// Snapshot reference for useSyncExternalStore (rebuilt on every registration change)
let commandsSnapshot: CommandItem[] = []

function updateCommandsSnapshot() {
  commandsSnapshot = getAllCommands()
}

function subscribeCommands(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function getCommandsSnapshot() {
  return commandsSnapshot
}

function getOpenSnapshot() {
  return openState
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

function registerCommands(commands: CommandItem[]): () => void {
  const key = String(++registrationCounter)
  commandGroups.set(key, commands)
  updateCommandsSnapshot()
  emitChange()

  return () => {
    commandGroups.delete(key)
    updateCommandsSnapshot()
    emitChange()
  }
}

function setOpen(value: boolean) {
  if (openState !== value) {
    openState = value
    emitChange()
  }
}

/**
 * Hook for interacting with the global command palette.
 *
 * - `registerCommands(items)` registers commands with the palette; returns a cleanup function.
 * - `open()` / `close()` programmatically control the palette.
 * - `commands` is the current list of all registered commands.
 * - `isOpen` reflects the palette's open state.
 */
export function useCommandPalette() {
  const commands = useSyncExternalStore(subscribeCommands, getCommandsSnapshot)
  const isOpen = useSyncExternalStore(subscribeCommands, getOpenSnapshot)

  const open = useCallback(() => setOpen(true), [])
  const close = useCallback(() => setOpen(false), [])
  const toggle = useCallback(() => setOpen(!getOpenSnapshot()), [])

  return {
    commands,
    isOpen,
    registerCommands,
    open,
    close,
    toggle,
  }
}

/**
 * Hook that registers commands on mount and cleans up on unmount.
 *
 * Note: `commands` should be memoized (e.g., via `useMemo` or a module-level constant)
 * to avoid re-registration on every render.
 */
export function useRegisterCommands(commands: CommandItem[]) {
  useEffect(() => {
    const cleanup = registerCommands(commands)
    return cleanup
  }, [commands])
}

/** Reset all module-level state (for testing only). */
export function _reset() {
  commandGroups.clear()
  openState = false
  registrationCounter = 0
  updateCommandsSnapshot()
  emitChange()
}

// Public API for non-hook contexts (e.g. tests, stories)
export { registerCommands }

// Exported for testing
export { setOpen as _setOpen, commandGroups as _commandGroups, updateCommandsSnapshot as _updateCommandsSnapshot }
