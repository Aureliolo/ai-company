import { useArtifactsStore } from '@/stores/artifacts'
import { ARTIFACT_TYPE_VALUES, type ArtifactType } from '@/api/types/enums'
import { formatLabel } from '@/utils/format'

const CONTENT_TYPE_OPTIONS = [
  { value: 'text/', label: 'Text' },
  { value: 'image/', label: 'Image' },
  { value: 'application/json', label: 'JSON' },
  { value: 'application/pdf', label: 'PDF' },
  { value: 'application/', label: 'Application' },
] as const

export function ArtifactFilters() {
  const searchQuery = useArtifactsStore((s) => s.searchQuery)
  const typeFilter = useArtifactsStore((s) => s.typeFilter)
  const createdByFilter = useArtifactsStore((s) => s.createdByFilter)
  const taskIdFilter = useArtifactsStore((s) => s.taskIdFilter)
  const contentTypeFilter = useArtifactsStore((s) => s.contentTypeFilter)
  const projectIdFilter = useArtifactsStore((s) => s.projectIdFilter)
  const setSearchQuery = useArtifactsStore((s) => s.setSearchQuery)
  const setTypeFilter = useArtifactsStore((s) => s.setTypeFilter)
  const setCreatedByFilter = useArtifactsStore((s) => s.setCreatedByFilter)
  const setTaskIdFilter = useArtifactsStore((s) => s.setTaskIdFilter)
  const setContentTypeFilter = useArtifactsStore((s) => s.setContentTypeFilter)
  const setProjectIdFilter = useArtifactsStore((s) => s.setProjectIdFilter)

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

      <input
        type="text"
        placeholder="Filter by agent..."
        value={createdByFilter ?? ''}
        onChange={(e) => setCreatedByFilter(e.target.value || null)}
        className="h-9 w-40 rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent"
        aria-label="Filter by creator agent"
      />

      <input
        type="text"
        placeholder="Filter by task..."
        value={taskIdFilter ?? ''}
        onChange={(e) => setTaskIdFilter(e.target.value || null)}
        className="h-9 w-40 rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent"
        aria-label="Filter by task ID"
      />

      <select
        value={contentTypeFilter ?? ''}
        onChange={(e) => setContentTypeFilter(e.target.value || null)}
        className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
        aria-label="Filter by content type"
      >
        <option value="">All content types</option>
        {CONTENT_TYPE_OPTIONS.map((ct) => (
          <option key={ct.value} value={ct.value}>{ct.label}</option>
        ))}
      </select>

      <input
        type="text"
        placeholder="Filter by project..."
        value={projectIdFilter ?? ''}
        onChange={(e) => setProjectIdFilter(e.target.value || null)}
        className="h-9 w-40 rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent"
        aria-label="Filter by project ID"
      />
    </div>
  )
}
