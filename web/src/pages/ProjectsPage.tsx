import { useCallback, useMemo, useState } from 'react'
import { AnimatePresence } from 'motion/react'
import { Plus, Trash2 } from 'lucide-react'
import { useProjectsData } from '@/hooks/useProjectsData'
import { useProjectsStore } from '@/stores/projects'
import { useToastStore } from '@/stores/toast'
import { Button } from '@/components/ui/button'
import { BulkActionBar } from '@/components/ui/bulk-action-bar'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { ErrorBanner } from '@/components/ui/error-banner'
import { ListHeader } from '@/components/ui/list-header'
import { formatNumber } from '@/utils/format'
import { ProjectsSkeleton } from './projects/ProjectsSkeleton'
import { ProjectFilters } from './projects/ProjectFilters'
import { ProjectGridView } from './projects/ProjectGridView'
import { ProjectCreateDrawer } from './projects/ProjectCreateDrawer'

export default function ProjectsPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(() => new Set())
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false)
  const [bulkDeleting, setBulkDeleting] = useState(false)
  const {
    filteredProjects,
    totalProjects,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useProjectsData()

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const clearSelection = useCallback(() => setSelectedIds(new Set()), [])

  const visibleIds = useMemo(
    () => new Set(filteredProjects.map((p) => p.id)),
    [filteredProjects],
  )
  const visibleSelected = useMemo(() => {
    const next = new Set<string>()
    for (const id of selectedIds) {
      if (visibleIds.has(id)) next.add(id)
    }
    return next
  }, [selectedIds, visibleIds])
  const selectedCount = visibleSelected.size

  const handleBulkDelete = useCallback(async () => {
    setBulkDeleting(true)
    const ids = [...visibleSelected]
    const result = await useProjectsStore.getState().batchDeleteProjects(ids)
    setBulkDeleting(false)
    setBulkDeleteOpen(false)
    clearSelection()
    if (result.failed === 0) {
      useToastStore.getState().add({
        variant: 'success',
        title: `Deleted ${formatNumber(result.succeeded)} project${result.succeeded === 1 ? '' : 's'}`,
      })
    } else {
      useToastStore.getState().add({
        variant: 'warning',
        title: `Deleted ${formatNumber(result.succeeded)} of ${formatNumber(ids.length)} projects`,
        description: result.failedReasons.length > 0 ? result.failedReasons.join('; ') : undefined,
      })
    }
  }, [visibleSelected, clearSelection])

  if (loading && totalProjects === 0) {
    return <ProjectsSkeleton />
  }

  return (
    <div className="space-y-section-gap">
      <ListHeader
        title="Projects"
        count={filteredProjects.length}
        countLabel={filteredProjects.length === totalProjects ? undefined : `${filteredProjects.length} of ${totalProjects}`}
        primaryAction={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus aria-hidden="true" />
            New project
          </Button>
        }
      />

      {error && (
        <ErrorBanner severity="error" title="Could not load projects" description={error} />
      )}

      {!wsConnected && !loading && (
        <ErrorBanner
          variant="offline"
          title="Real-time updates disconnected"
          description={wsSetupError ?? 'Data may be stale until the connection recovers.'}
        />
      )}

      <ProjectFilters />
      <ProjectGridView
        projects={filteredProjects}
        onToggleSelect={handleToggleSelect}
        selectedIds={visibleSelected}
      />

      <AnimatePresence>
        {selectedCount > 0 && (
          <BulkActionBar
            selectedCount={selectedCount}
            onClear={clearSelection}
            loading={bulkDeleting}
            ariaLabel="Project bulk actions"
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
        title={`Delete ${formatNumber(selectedCount)} project${selectedCount === 1 ? '' : 's'}?`}
        description="This will permanently remove the selected projects. Associated tasks remain, but their project link will be broken. This action cannot be undone."
        confirmLabel={`Delete ${formatNumber(selectedCount)}`}
        variant="destructive"
        loading={bulkDeleting}
        onConfirm={handleBulkDelete}
      />

      <ProjectCreateDrawer open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
