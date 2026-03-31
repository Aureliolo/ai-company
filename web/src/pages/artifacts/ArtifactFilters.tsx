import { useArtifactsStore } from '@/stores/artifacts'
import { ARTIFACT_TYPE_VALUES, type ArtifactType } from '@/api/types'
import { formatLabel } from '@/utils/format'

export function ArtifactFilters() {
  const searchQuery = useArtifactsStore((s) => s.searchQuery)
  const typeFilter = useArtifactsStore((s) => s.typeFilter)
  const setSearchQuery = useArtifactsStore((s) => s.setSearchQuery)
  const setTypeFilter = useArtifactsStore((s) => s.setTypeFilter)

  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        type="text"
        placeholder="Search artifacts..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="h-9 w-64 rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent"
        aria-label="Search artifacts"
      />

      <select
        value={typeFilter ?? ''}
        onChange={(e) => {
          const val = e.target.value
          if (!val) {
            setTypeFilter(null)
            return
          }
          if (ARTIFACT_TYPE_VALUES.includes(val as ArtifactType)) {
            setTypeFilter(val as ArtifactType)
          }
        }}
        className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
        aria-label="Filter by type"
      >
        <option value="">All types</option>
        {ARTIFACT_TYPE_VALUES.map((t) => (
          <option key={t} value={t}>{formatLabel(t)}</option>
        ))}
      </select>
    </div>
  )
}
