import { Command } from 'cmdk'
import { FocusScope } from '@radix-ui/react-focus-scope'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CommandItem } from '@/hooks/useCommandPalette'
import { useCommandPalette } from '@/hooks/useCommandPalette'

const RECENT_STORAGE_KEY = 'so_recent_commands'
const MAX_RECENT = 5

function getRecentIds(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter((v): v is string => typeof v === 'string').slice(0, MAX_RECENT)
  } catch (err) {
    if (import.meta.env.DEV) {
      console.warn('Failed to read recent commands from localStorage:', err)
    }
    return []
  }
}

function addRecentId(id: string) {
  try {
    const recent = getRecentIds().filter((r) => r !== id)
    recent.unshift(id)
    localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(recent.slice(0, MAX_RECENT)))
  } catch {
    // Best-effort convenience feature -- never block command execution
  }
}

export interface CommandPaletteProps {
  className?: string
}

export function CommandPalette({ className }: CommandPaletteProps) {
  const { commands, isOpen, close, toggle } = useCommandPalette()
  const [search, setSearch] = useState('')
  const [scope, setScope] = useState<'global' | 'local'>('global')
  // Global keyboard shortcuts: Cmd+K / Ctrl+K to toggle, Escape to close
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        toggle()
      } else if (e.key === 'Escape' && isOpen) {
        e.preventDefault()
        close()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [toggle, close, isOpen])

  // Reset search and scope when palette opens
  useEffect(() => {
    if (isOpen) {
      setSearch('') // eslint-disable-line @eslint-react/set-state-in-effect -- intentional reset on open
      setScope('global') // eslint-disable-line @eslint-react/set-state-in-effect -- intentional reset on open
    }
  }, [isOpen])

  const filteredCommands = useMemo(() => {
    return commands.filter((cmd) => {
      const cmdScope = cmd.scope ?? 'global'
      return scope === 'global' ? true : cmdScope === 'local'
    })
  }, [commands, scope])

  const grouped = useMemo(() => {
    const groups = new Map<string, CommandItem[]>()
    for (const cmd of filteredCommands) {
      const existing = groups.get(cmd.group) ?? []
      existing.push(cmd)
      groups.set(cmd.group, existing)
    }
    return groups
  }, [filteredCommands])

  // Recent items (only shown when search is empty)
  // Re-read recent items each time the palette opens
  const recentIds = useMemo(() => getRecentIds(), [isOpen]) // eslint-disable-line @eslint-react/exhaustive-deps
  const recentItems = useMemo(() => {
    if (search) return []
    return recentIds
      .map((id) => commands.find((c) => c.id === id))
      .filter((c): c is CommandItem => {
        if (c === undefined) return false
        const cmdScope = c.scope ?? 'global'
        return scope === 'global' ? true : cmdScope === 'local'
      })
  }, [search, recentIds, commands, scope])

  const recentIdSet = useMemo(
    () => new Set(recentItems.map((c) => c.id)),
    [recentItems],
  )

  const handleSelect = useCallback(
    (cmd: CommandItem) => {
      addRecentId(cmd.id)
      try {
        cmd.action()
      } catch (err) {
        if (import.meta.env.DEV) {
          console.error('Command action failed:', err)
        }
      }
      close()
    },
    [close],
  )

  const handleScopeToggle = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Tab' && commands.some((c) => c.scope === 'local')) {
        e.preventDefault()
        setScope((prev) => (prev === 'global' ? 'local' : 'global'))
      }
    },
    [commands],
  )

  if (!isOpen) return null

  const hasLocalCommands = commands.some((c) => c.scope === 'local')

  return (
    <div
      className="fixed inset-0 z-50"
      onKeyDown={handleScopeToggle}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={close}
        aria-hidden="true"
      />
      {/* Panel */}
      <div className="flex items-start justify-center pt-[15vh]">
        <FocusScope trapped loop>
        <Command
          className={cn(
            'relative w-full max-w-[640px] rounded-xl border border-border-bright bg-surface shadow-lg',
            className,
          )}
          label="Command palette"
        >
          {/* Search input */}
          <div className="flex items-center gap-3 border-b border-border px-4">
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <Command.Input
              value={search}
              onValueChange={setSearch}
              placeholder={scope === 'global' ? 'Search commands...' : 'Search page commands...'}
              className="flex-1 bg-transparent py-3 text-base text-foreground placeholder:text-muted-foreground outline-none"
            />
            {hasLocalCommands && (
              <span className="shrink-0 rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                Tab: {scope}
              </span>
            )}
          </div>

          <Command.List className="max-h-[320px] overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
              No results found.
            </Command.Empty>

            {/* Recent items */}
            {recentItems.length > 0 && (
              <Command.Group heading="Recent" className="mb-1">
                {recentItems.map((cmd) => (
                  <CommandItemRow key={`recent-${cmd.id}`} item={cmd} onSelect={handleSelect} />
                ))}
              </Command.Group>
            )}

            {/* Command groups */}
            {[...grouped.entries()].map(([groupName, items]) => (
              <Command.Group
                key={groupName}
                heading={groupName}
                className="mb-1"
              >
                {items.filter((cmd) => !recentIdSet.has(cmd.id)).map((cmd) => (
                  <CommandItemRow key={cmd.id} item={cmd} onSelect={handleSelect} />
                ))}
              </Command.Group>
            ))}
          </Command.List>

          {/* Footer hint */}
          <div className="flex items-center gap-4 border-t border-border px-4 py-2 text-[10px] text-muted-foreground">
            <span>
              <kbd className="rounded border border-border px-1">Enter</kbd> select
            </span>
            <span>
              <kbd className="rounded border border-border px-1">Esc</kbd> close
            </span>
            {hasLocalCommands && (
              <span>
                <kbd className="rounded border border-border px-1">Tab</kbd> scope
              </span>
            )}
          </div>
        </Command>
        </FocusScope>
      </div>
    </div>
  )
}

function CommandItemRow({
  item,
  onSelect,
}: {
  item: CommandItem
  onSelect: (item: CommandItem) => void
}) {
  const Icon = item.icon
  return (
    <Command.Item
      value={[item.label, ...(item.keywords ?? [])].join(' ')}
      onSelect={() => onSelect(item)}
      className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm text-foreground data-[selected=true]:bg-card-hover"
    >
      {Icon && <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />}
      <div className="flex-1">
        <span>{item.label}</span>
        {item.description && (
          <span className="ml-2 text-xs text-muted-foreground">{item.description}</span>
        )}
      </div>
      {item.shortcut && (
        <div className="flex gap-1">
          {item.shortcut.map((key) => (
            <kbd
              key={key}
              className="rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground"
            >
              {key}
            </kbd>
          ))}
        </div>
      )}
    </Command.Item>
  )
}
