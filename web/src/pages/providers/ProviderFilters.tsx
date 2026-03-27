import { useProvidersStore } from '@/stores/providers'
import type { ProviderHealthStatus } from '@/api/types'
import type { ProviderSortKey } from '@/utils/providers'

const HEALTH_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All health' },
  { value: 'up', label: 'Up' },
  { value: 'degraded', label: 'Degraded' },
  { value: 'down', label: 'Down' },
]

const SORT_OPTIONS: { value: ProviderSortKey; label: string }[] = [
  { value: 'name', label: 'Name' },
  { value: 'health', label: 'Health' },
  { value: 'model_count', label: 'Models' },
]

const VALID_HEALTH: ReadonlySet<string> = new Set(['up', 'degraded', 'down'])
const VALID_SORT: ReadonlySet<string> = new Set(['name', 'health', 'model_count'])

export function ProviderFilters() {
  const searchQuery = useProvidersStore((s) => s.searchQuery)
  const healthFilter = useProvidersStore((s) => s.healthFilter)
  const sortBy = useProvidersStore((s) => s.sortBy)
  const setSearchQuery = useProvidersStore((s) => s.setSearchQuery)
  const setHealthFilter = useProvidersStore((s) => s.setHealthFilter)
  const setSortBy = useProvidersStore((s) => s.setSortBy)

  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        type="text"
        placeholder="Search providers..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="h-8 rounded-md border border-border bg-bg-surface px-3 text-sm text-foreground placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-accent"
      />

      <select
        value={healthFilter ?? ''}
        onChange={(e) => {
          const v = e.target.value
          setHealthFilter(v && VALID_HEALTH.has(v) ? (v as ProviderHealthStatus) : null)
        }}
        className="h-8 rounded-md border border-border bg-bg-surface px-2 text-sm text-foreground"
      >
        {HEALTH_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      <select
        value={sortBy}
        onChange={(e) => {
          const v = e.target.value
          if (VALID_SORT.has(v)) setSortBy(v as ProviderSortKey)
        }}
        className="h-8 rounded-md border border-border bg-bg-surface px-2 text-sm text-foreground"
      >
        {SORT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            Sort: {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
