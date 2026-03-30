import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SettingEntry } from '@/api/types'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { SettingRow } from './SettingRow'

interface NamespaceSettingRowProps {
  entry: SettingEntry
  dirtyValues: ReadonlyMap<string, string>
  onValueChange: (ck: string, v: string) => void
  savingKeys: ReadonlySet<string>
  controllerDisabledMap: ReadonlyMap<string, boolean>
  changedKeys?: ReadonlySet<string>
}

function NamespaceSettingRow({
  entry,
  dirtyValues,
  onValueChange,
  savingKeys,
  controllerDisabledMap,
  changedKeys,
}: NamespaceSettingRowProps) {
  const ck = `${entry.definition.namespace}/${entry.definition.key}`
  return (
    <ErrorBoundary level="component">
      <SettingRow
        entry={entry}
        dirtyValue={dirtyValues.get(ck)}
        onChange={(value) => onValueChange(ck, value)}
        saving={savingKeys.has(ck)}
        controllerDisabled={controllerDisabledMap.get(ck)}
        flash={changedKeys?.has(ck)}
      />
    </ErrorBoundary>
  )
}

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
  /** Set of composite keys that changed externally (flash animation). */
  changedKeys?: ReadonlySet<string>
  /** Hide the collapsible header (when tab bar serves as the header). */
  hideHeader?: boolean
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
  changedKeys,
  hideHeader,
}: NamespaceSectionProps) {
  const [collapsed, setCollapsed] = useState(false)
  const isOpen = hideHeader || forceOpen || !collapsed
  const groups = groupByGroup(entries)
  const contentId = `ns-${displayName.replace(/\s+/g, '-').toLowerCase()}-content`

  return (
    <section className={cn('rounded-lg border border-border bg-card', hideHeader && 'border-0 bg-transparent')}>
      {!hideHeader && (
        <button
          type="button"
          onClick={() => { if (!forceOpen) setCollapsed((v) => !v) }}
          className={cn(
            'flex w-full items-center gap-3 px-4 py-3',
            'text-left transition-colors hover:bg-card-hover',
          )}
          aria-expanded={isOpen}
          aria-controls={contentId}
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
      )}

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            id={contentId}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 35 }}
            className={cn('overflow-hidden', !hideHeader && 'border-t border-border')}
          >
            <div className="px-4 py-2">
              {[...groups.entries()].map(([group, groupEntries]) => (
                <div key={group} className="py-2">
                  {groups.size > 1 && (
                    <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-text-muted">
                      {group}
                    </h3>
                  )}
                  <div className="space-y-1">
                    {groupEntries.map((entry, i) => (
                      <motion.div
                        key={`${entry.definition.namespace}/${entry.definition.key}`}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.03, duration: 0.2 }}
                      >
                        <NamespaceSettingRow
                          entry={entry}
                          dirtyValues={dirtyValues}
                          onValueChange={onValueChange}
                          savingKeys={savingKeys}
                          controllerDisabledMap={controllerDisabledMap}
                          changedKeys={changedKeys}
                        />
                      </motion.div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
