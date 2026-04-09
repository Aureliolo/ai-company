/**
 * Entity catalog section -- card grid with filter tabs.
 */
import { Search, Shapes } from 'lucide-react'
import { useOntologyStore } from '@/stores/ontology'
import { SectionCard } from '@/components/ui/section-card'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { EntityCard } from './EntityCard'
import type { EntityResponse } from '@/api/endpoints/ontology'

const TIER_OPTIONS = [
  { value: 'all' as const, label: 'All' },
  { value: 'core' as const, label: 'Core' },
  { value: 'user' as const, label: 'User' },
]

interface EntityCatalogProps {
  entities: readonly EntityResponse[]
}

export function EntityCatalog({ entities }: EntityCatalogProps) {
  const tierFilter = useOntologyStore((s) => s.tierFilter)
  const searchQuery = useOntologyStore((s) => s.searchQuery)
  const setTierFilter = useOntologyStore((s) => s.setTierFilter)
  const setSearchQuery = useOntologyStore((s) => s.setSearchQuery)
  const setSelectedEntity = useOntologyStore((s) => s.setSelectedEntity)

  return (
    <SectionCard title="Entity Catalog" icon={Shapes}>
      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <SegmentedControl
          label="Filter by tier"
          value={tierFilter}
          onChange={setTierFilter}
          options={TIER_OPTIONS}
          size="sm"
        />

        <div className="relative">
          <Search aria-hidden="true" className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search entities..."
            className="h-8 w-full rounded-md border border-border bg-surface pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent sm:w-56"
            aria-label="Search entities"
          />
        </div>
      </div>

      {/* Card grid */}
      {entities.length === 0 ? (
        <EmptyState
          title="No entities found"
          description={
            searchQuery || tierFilter !== 'all'
              ? 'Try adjusting your search or filter criteria.'
              : 'Entity definitions will appear here once registered.'
          }
        />
      ) : (
        <StaggerGroup className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 lg:grid-cols-3">
          {entities.map((entity) => (
            <StaggerItem key={entity.name}>
              <EntityCard
                entity={entity}
                onClick={() => setSelectedEntity(entity)}
              />
            </StaggerItem>
          ))}
        </StaggerGroup>
      )}
    </SectionCard>
  )
}
