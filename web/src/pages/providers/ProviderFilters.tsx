import { useProvidersStore } from '@/stores/providers'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import type { ProviderHealthStatus } from '@/api/types'
import type { ProviderSortKey } from '@/utils/providers'

const HEALTH_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All health' },
  { value: 'up', label: 'Up' },
  { value: 'degraded', label: 'Degraded' },
  { value: 'down', label: 'Down' },
  { value: 'unknown', label: 'Unknown' },
]

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: 'name', label: 'Name' },
  { value: 'health', label: 'Health' },
  { value: 'model_count', label: 'Models' },
]

const VALID_HEALTH: ReadonlySet<string> = new Set(['up', 'degraded', 'down', 'unknown'])
const VALID_SORT: ReadonlySet<string> = new Set(['name', 'health', 'model_count'])

export function ProviderFilters() {
  const searchQuery = useProvidersStore((s) => s.searchQuery)
  const healthFilter = useProvidersStore((s) => s.healthFilter)
  const sortBy = useProvidersStore((s) => s.sortBy)
  const setSearchQuery = useProvidersStore((s) => s.setSearchQuery)
  const setHealthFilter = useProvidersStore((s) => s.setHealthFilter)
  const setSortBy = useProvidersStore((s) => s.setSortBy)

  return (
    <div className="flex flex-wrap items-end gap-3">
      <InputField
        label="Search"
        placeholder="Search providers..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
      />

      <SelectField
        label="Health"
        options={HEALTH_OPTIONS}
        value={healthFilter ?? ''}
        onChange={(v) => {
          setHealthFilter(v && VALID_HEALTH.has(v) ? (v as ProviderHealthStatus) : null)
        }}
      />

      <SelectField
        label="Sort by"
        options={SORT_OPTIONS}
        value={sortBy}
        onChange={(v) => {
          if (VALID_SORT.has(v)) setSortBy(v as ProviderSortKey)
        }}
      />
    </div>
  )
}
