import { useCallback, useMemo, useState } from 'react'
import { AnimatePresence } from 'motion/react'
import { Plus, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router'
import { ROUTES } from '@/router/routes'
import { useWorkflowsData } from '@/hooks/useWorkflowsData'
import { useWorkflowsStore } from '@/stores/workflows'
import { Button } from '@/components/ui/button'
import { BulkActionBar } from '@/components/ui/bulk-action-bar'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { ErrorBanner } from '@/components/ui/error-banner'
import { ListHeader } from '@/components/ui/list-header'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { useToastStore } from '@/stores/toast'
import { formatNumber } from '@/utils/format'
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
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(() => new Set())
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false)
  const [bulkDeleting, setBulkDeleting] = useState(false)
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

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const clearSelection = useCallback(() => setSelectedIds(new Set()), [])

  const selectedCount = selectedIds.size
  const visibleIds = useMemo(
    () => new Set(filteredWorkflows.map((w) => w.id)),
    [filteredWorkflows],
  )
  // Prune selection to workflows that are still visible after filter/refetch.
  const visibleSelected = useMemo(() => {
    const next = new Set<string>()
    for (const id of selectedIds) {
      if (visibleIds.has(id)) next.add(id)
    }
    return next
  }, [selectedIds, visibleIds])

  const handleBulkDelete = useCallback(async () => {
    setBulkDeleting(true)
    const ids = [...visibleSelected]
    const results = await Promise.allSettled(
      ids.map(async (id) => {
        const ok = await useWorkflowsStore.getState().deleteWorkflow(id)
        if (!ok) throw new Error('delete returned false')
        return id
      }),
    )
    const succeeded = results.filter((r) => r.status === 'fulfilled').length
    const failed = ids.length - succeeded
    setBulkDeleting(false)
    setBulkDeleteOpen(false)
    clearSelection()
    if (failed === 0) {
      useToastStore.getState().add({
        variant: 'success',
        title: `Deleted ${formatNumber(succeeded)} workflow${succeeded === 1 ? '' : 's'}`,
      })
    } else {
      useToastStore.getState().add({
        variant: 'warning',
        title: `Deleted ${formatNumber(succeeded)} of ${formatNumber(ids.length)} workflows`,
        description: `${formatNumber(failed)} failed. Please retry.`,
      })
    }
  }, [visibleSelected, clearSelection])

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
      <ListHeader
        title="Workflows"
        count={filteredWorkflows.length}
        countLabel={filteredWorkflows.length === totalWorkflows ? undefined : `${filteredWorkflows.length} of ${totalWorkflows}`}
        primaryAction={
          <div className="flex items-center gap-2">
            <SegmentedControl
              label="View mode"
              value={viewMode}
              onChange={setViewMode}
              options={VIEW_MODE_OPTIONS}
              size="sm"
            />
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus aria-hidden="true" />
              New workflow
            </Button>
          </div>
        }
      />

      {error && (
        <ErrorBanner severity="error" title="Could not load workflows" description={error} />
      )}

      <WorkflowFilters />
      {viewMode === 'grid' ? (
        <WorkflowGridView
          workflows={filteredWorkflows}
          onDelete={handleDelete}
          onDuplicate={handleDuplicate}
          onToggleSelect={handleToggleSelect}
          selectedIds={visibleSelected}
        />
      ) : (
        <WorkflowTableView
          workflows={filteredWorkflows}
          onDelete={handleDelete}
          onDuplicate={handleDuplicate}
          onToggleSelect={handleToggleSelect}
          selectedIds={visibleSelected}
        />
      )}

      <AnimatePresence>
        {selectedCount > 0 && (
          <BulkActionBar
            selectedCount={selectedCount}
            onClear={clearSelection}
            loading={bulkDeleting}
            ariaLabel="Workflow bulk actions"
          >
            <Button
              size="sm"
              variant="outline"
              className="gap-1 border-danger/30 text-danger hover:bg-danger/10"
              onClick={() => setBulkDeleteOpen(true)}
              disabled={bulkDeleting}
            >
              <Trash2 className="size-3.5" />
              Delete {formatNumber(selectedCount)}
            </Button>
          </BulkActionBar>
        )}
      </AnimatePresence>

      <ConfirmDialog
        open={bulkDeleteOpen}
        onOpenChange={(open) => { if (!open && !bulkDeleting) setBulkDeleteOpen(false) }}
        title={`Delete ${formatNumber(selectedCount)} workflow${selectedCount === 1 ? '' : 's'}?`}
        description="This will permanently remove every selected workflow definition and its version history. This action cannot be undone."
        confirmLabel={`Delete ${formatNumber(selectedCount)}`}
        variant="destructive"
        loading={bulkDeleting}
        onConfirm={handleBulkDelete}
      />

      <WorkflowCreateDrawer open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
