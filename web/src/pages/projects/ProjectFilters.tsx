import { useProjectsStore } from '@/stores/projects'
import { PROJECT_STATUS_VALUES, type ProjectStatus } from '@/api/types/enums'
import { formatLabel } from '@/utils/format'

export function ProjectFilters() {
  const searchQuery = useProjectsStore((s) => s.searchQuery)
  const statusFilter = useProjectsStore((s) => s.statusFilter)
  const setSearchQuery = useProjectsStore((s) => s.setSearchQuery)
  const setStatusFilter = useProjectsStore((s) => s.setStatusFilter)

  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        type="text"
        placeholder="Search projects..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="h-9 w-64 rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent"
        aria-label="Search projects"
      />

      <select
        value={statusFilter ?? ''}
        onChange={(e) => {
          const val = e.target.value
          if (!val) {
            setStatusFilter(null)
            return
          }
          if (PROJECT_STATUS_VALUES.includes(val as ProjectStatus)) {
            setStatusFilter(val as ProjectStatus)
          }
        }}
        className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
        aria-label="Filter by status"
      >
        <option value="">All statuses</option>
        {PROJECT_STATUS_VALUES.map((s) => (
          <option key={s} value={s}>{formatLabel(s)}</option>
        ))}
      </select>
    </div>
  )
}
