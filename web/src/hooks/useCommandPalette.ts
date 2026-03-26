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
  /** Whether this item is pinned to the top. */
  pinned?: boolean
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

// Snapshot references for useSyncExternalStore (must be referentially stable when unchanged)
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
 * - `registerCommands(items)` registers page-local commands; returns a cleanup function.
 * - `open()` / `close()` programmatically control the palette.
 * - `commands` is the current list of all registered commands.
 * - `isOpen` reflects the palette's open state.
 */
export function useCommandPalette() {
  const commands = useSyncExternalStore(subscribeCommands, getCommandsSnapshot)
  const isOpen = useSyncExternalStore(subscribeCommands, getOpenSnapshot)

  const open = useCallback(() => setOpen(true), [])
  const close = useCallback(() => setOpen(false), [])
  const toggle = useCallback(() => setOpen(!openState), [])

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
 */
export function useRegisterCommands(commands: CommandItem[]) {
  useEffect(() => {
    const cleanup = registerCommands(commands)
    return cleanup
  }, [commands])
}

// Exported for testing
export { setOpen as _setOpen, commandGroups as _commandGroups, updateCommandsSnapshot as _updateCommandsSnapshot }
