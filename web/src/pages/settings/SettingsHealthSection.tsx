import type { SettingNamespace } from '@/api/types'
import { cn } from '@/lib/utils'
import { NAMESPACE_DISPLAY_NAMES } from '@/utils/constants'

export interface NamespaceTabBarProps {
  namespaces: readonly SettingNamespace[]
  activeNamespace: SettingNamespace | null
  onSelect: (ns: SettingNamespace | null) => void
  namespaceCounts: ReadonlyMap<string, number>
  namespaceIcons?: Partial<Record<SettingNamespace, React.ReactNode>>
}

export function NamespaceTabBar({
  namespaces,
  activeNamespace,
  onSelect,
  namespaceCounts,
  namespaceIcons,
}: NamespaceTabBarProps) {
  return (
    <div
      className="flex flex-wrap items-center gap-1 rounded-lg border border-border bg-card px-2 py-1.5"
      role="tablist"
      aria-label="Setting namespaces"
    >
      <button
        type="button"
        role="tab"
        aria-selected={activeNamespace === null}
        onClick={() => onSelect(null)}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-xs font-semibold transition-all duration-200',
          activeNamespace === null
            ? 'bg-accent/10 text-accent'
            : 'text-text-secondary hover:bg-card-hover hover:text-foreground',
        )}
      >
        All
      </button>
      {namespaces.map((ns) => {
        const count = namespaceCounts.get(ns) ?? 0
        if (count === 0) return null
        const icon = namespaceIcons?.[ns]
        return (
          <button
            key={ns}
            type="button"
            role="tab"
            aria-selected={activeNamespace === ns}
            onClick={() => onSelect(ns)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-xs font-semibold transition-all duration-200',
              activeNamespace === ns
                ? 'bg-accent/10 text-accent'
                : 'text-text-secondary hover:bg-card-hover hover:text-foreground',
            )}
          >
            {icon && <span className="shrink-0">{icon}</span>}
            {NAMESPACE_DISPLAY_NAMES[ns]}
            <span className="font-normal text-text-muted">{count}</span>
          </button>
        )
      })}
    </div>
  )
}
