import { useWorkflowsStore } from '@/stores/workflows'
import { formatLabel } from '@/utils/format'

const WORKFLOW_TYPES = [
  'sequential_pipeline',
  'parallel_execution',
  'kanban',
  'agile_kanban',
] as const

export function WorkflowFilters() {
  const searchQuery = useWorkflowsStore((s) => s.searchQuery)
  const workflowTypeFilter = useWorkflowsStore((s) => s.workflowTypeFilter)
  const setSearchQuery = useWorkflowsStore((s) => s.setSearchQuery)
  const setWorkflowTypeFilter = useWorkflowsStore((s) => s.setWorkflowTypeFilter)

  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        type="text"
        placeholder="Search workflows..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="h-9 w-64 rounded-md border border-border bg-surface px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent"
        aria-label="Search workflows"
      />

      <select
        value={workflowTypeFilter ?? ''}
        onChange={(e) => {
          const val = e.target.value
          setWorkflowTypeFilter(val || null)
        }}
        className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-foreground"
        aria-label="Filter by workflow type"
      >
        <option value="">All types</option>
        {WORKFLOW_TYPES.map((t) => (
          <option key={t} value={t}>
            {formatLabel(t)}
          </option>
        ))}
      </select>
    </div>
  )
}
