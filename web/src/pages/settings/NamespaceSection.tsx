import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SettingEntry } from '@/api/types'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { SettingRow } from './SettingRow'

export interface NamespaceSectionProps {
  displayName: string
  icon: React.ReactNode
  entries: SettingEntry[]
  dirtyValues: ReadonlyMap<string, string>
  onValueChange: (compositeKey: string, value: string) => void
  savingKeys: ReadonlySet<string>
  /** Map of composite key -> boolean indicating if its controller is disabled. */
  controllerDisabledMap: ReadonlyMap<string, boolean>
  /** Whether the section is forced open (e.g. during search). */
  forceOpen?: boolean
}

function groupByGroup(entries: SettingEntry[]): Map<string, SettingEntry[]> {
  const groups = new Map<string, SettingEntry[]>()
  for (const entry of entries) {
    const group = entry.definition.group
    const existing = groups.get(group)
    if (existing) {
      existing.push(entry)
    } else {
      groups.set(group, [entry])
    }
  }
  return groups
}

export function NamespaceSection({
  displayName,
  icon,
  entries,
  dirtyValues,
  onValueChange,
  savingKeys,
  controllerDisabledMap,
  forceOpen,
}: NamespaceSectionProps) {
  const [collapsed, setCollapsed] = useState(false)
  const isOpen = forceOpen || !collapsed
  const groups = groupByGroup(entries)

  return (
    <section className="rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-card-hover"
        aria-expanded={isOpen}
      >
        <span className="text-text-secondary">{icon}</span>
        <h2 className="text-sm font-semibold text-foreground">{displayName}</h2>
        <span className="ml-1 text-xs text-text-muted">({entries.length})</span>
        <ChevronDown
          className={cn(
            'ml-auto size-4 text-text-muted transition-transform duration-200',
            isOpen && 'rotate-180',
          )}
          aria-hidden
        />
      </button>

      {isOpen && (
        <div className="border-t border-border px-4 py-2">
          {[...groups.entries()].map(([group, groupEntries]) => (
            <div key={group} className="py-2">
              {groups.size > 1 && (
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-text-muted">
                  {group}
                </h3>
              )}
              <div className="space-y-1">
                {groupEntries.map((entry) => {
                  const compositeKey = `${entry.definition.namespace}/${entry.definition.key}`
                  return (
                    <ErrorBoundary key={compositeKey} level="component">
                      <SettingRow
                        entry={entry}
                        dirtyValue={dirtyValues.get(compositeKey)}
                        onChange={(value) => onValueChange(compositeKey, value)}
                        saving={savingKeys.has(compositeKey)}
                        controllerDisabled={controllerDisabledMap.get(compositeKey)}
                      />
                    </ErrorBoundary>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
