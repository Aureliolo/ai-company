import { useCallback, useState } from 'react'
import { AlertTriangle, Plus } from 'lucide-react'
import { useNavigate } from 'react-router'
import { ROUTES } from '@/router/routes'
import { useWorkflowsData } from '@/hooks/useWorkflowsData'
import { useWorkflowsStore } from '@/stores/workflows'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'
import { Button } from '@/components/ui/button'
import { WorkflowsSkeleton } from './workflows/WorkflowsSkeleton'
import { WorkflowFilters } from './workflows/WorkflowFilters'
import { WorkflowGridView } from './workflows/WorkflowGridView'
import { WorkflowCreateDrawer } from './workflows/WorkflowCreateDrawer'

export default function WorkflowsPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const navigate = useNavigate()
  const addToast = useToastStore((s) => s.add)
  const {
    filteredWorkflows,
    totalWorkflows,
    loading,
    error,
  } = useWorkflowsData()

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await useWorkflowsStore.getState().deleteWorkflow(id)
        addToast({ variant: 'success', title: 'Workflow deleted' })
      } catch (err) {
        addToast({ variant: 'error', title: 'Delete failed', description: getErrorMessage(err) })
      }
    },
    [addToast],
  )

  const handleDuplicate = useCallback(
    async (id: string) => {
      try {
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
        addToast({ variant: 'success', title: 'Workflow duplicated' })
        navigate(`${ROUTES.WORKFLOW_EDITOR}?id=${encodeURIComponent(created.id)}`)
      } catch (err) {
        addToast({ variant: 'error', title: 'Duplicate failed', description: getErrorMessage(err) })
      }
    },
    [addToast, navigate],
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
      <WorkflowGridView
        workflows={filteredWorkflows}
        onDelete={handleDelete}
        onDuplicate={handleDuplicate}
      />

      <WorkflowCreateDrawer open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
