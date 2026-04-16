import { useCallback, useState } from 'react'
import { AlertTriangle, Plus } from 'lucide-react'
import { useNavigate } from 'react-router'
import { ROUTES } from '@/router/routes'
import { useWorkflowsData } from '@/hooks/useWorkflowsData'
import { useWorkflowsStore } from '@/stores/workflows'
import { Button } from '@/components/ui/button'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { WorkflowsSkeleton } from './workflows/WorkflowsSkeleton'
import { WorkflowFilters } from './workflows/WorkflowFilters'
import { WorkflowGridView } from './workflows/WorkflowGridView'
import { WorkflowTableView } from './workflows/WorkflowTableView'
import { WorkflowCreateDrawer } from './workflows/WorkflowCreateDrawer'

type ViewMode = 'grid' | 'table'

const VIEW_MODE_OPTIONS = [
  { value: 'grid' as const, label: 'Grid' },
  { value: 'table' as const, label: 'Table' },
]

export default function WorkflowsPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const navigate = useNavigate()
  const {
    filteredWorkflows,
    totalWorkflows,
    loading,
    error,
  } = useWorkflowsData()

  const handleDelete = useCallback(async (id: string) => {
    // Store owns success/error UX (toast + surgical rollback on failure).
    // Caller does not need to act on the boolean sentinel; WS updates drive
    // the authoritative list state.
    await useWorkflowsStore.getState().deleteWorkflow(id)
  }, [])

  const handleDuplicate = useCallback(
    async (id: string) => {
      const workflows = useWorkflowsStore.getState().workflows
      const source = workflows.find((w) => w.id === id)
      if (!source) return
      const created = await useWorkflowsStore.getState().createWorkflow({
        name: `${source.name} (Copy)`,
        description: source.description || undefined,
        workflow_type: source.workflow_type,
        nodes: source.nodes.map((n) => ({ ...n })),
        edges: source.edges.map((e) => ({ ...e })),
      })
      if (!created) return
      navigate(`${ROUTES.WORKFLOW_EDITOR}?id=${encodeURIComponent(created.id)}`)
    },
    [navigate],
  )

  if (loading && totalWorkflows === 0) {
    return <WorkflowsSkeleton />
  }

  return (
    <div className="space-y-section-gap">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Workflows</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">
            {filteredWorkflows.length} of {totalWorkflows}
          </span>
          <SegmentedControl
            label="View mode"
            value={viewMode}
            onChange={setViewMode}
            options={VIEW_MODE_OPTIONS}
            size="sm"
          />
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-1 size-4" />
            Create Workflow
          </Button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      <WorkflowFilters />
      {viewMode === 'grid' ? (
        <WorkflowGridView
          workflows={filteredWorkflows}
          onDelete={handleDelete}
          onDuplicate={handleDuplicate}
        />
      ) : (
        <WorkflowTableView
          workflows={filteredWorkflows}
          onDelete={handleDelete}
          onDuplicate={handleDuplicate}
        />
      )}

      <WorkflowCreateDrawer open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
