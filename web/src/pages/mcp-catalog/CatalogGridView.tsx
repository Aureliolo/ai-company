import { Package } from 'lucide-react'
import type { McpCatalogEntry } from '@/api/types'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { CatalogEntryCard } from './CatalogEntryCard'

export interface CatalogGridViewProps {
  entries: readonly McpCatalogEntry[]
  installedEntryIds: ReadonlySet<string>
  onSelect: (entry: McpCatalogEntry) => void
  onInstall: (entry: McpCatalogEntry) => void
  emptyTitle?: string
  emptyDescription?: string
}

export function CatalogGridView({
  entries,
  installedEntryIds,
  onSelect,
  onInstall,
  emptyTitle = 'No results',
  emptyDescription = 'Try a different search query.',
}: CatalogGridViewProps) {
  if (entries.length === 0) {
    return (
      <EmptyState
        icon={Package}
        title={emptyTitle}
        description={emptyDescription}
      />
    )
  }

  return (
    <StaggerGroup className="grid grid-cols-3 gap-grid-gap max-[1023px]:grid-cols-2 max-[767px]:grid-cols-1">
      {entries.map((entry) => (
        <StaggerItem key={entry.id}>
          <CatalogEntryCard
            entry={entry}
            installed={installedEntryIds.has(entry.id)}
            onSelect={() => onSelect(entry)}
            onInstall={() => onInstall(entry)}
          />
        </StaggerItem>
      ))}
    </StaggerGroup>
  )
}
