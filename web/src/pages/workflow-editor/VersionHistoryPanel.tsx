import { Clock, GitCompare, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Drawer } from '@/components/ui/drawer'
import { Skeleton } from '@/components/ui/skeleton'
import { useWorkflowEditorStore } from '@/stores/workflow-editor'
import { useState } from 'react'
import { formatRelativeTime } from '@/utils/format'
import type { WorkflowDefinition, WorkflowDefinitionVersionSummary } from '@/api/types'

export interface VersionCardProps {
  v: WorkflowDefinitionVersionSummary
  definition: WorkflowDefinition | null
  saving: boolean
  onCompare: (version: WorkflowDefinitionVersionSummary) => void
  onRestore: (version: number) => void
}

export function VersionCard({ v, definition, saving, onCompare, onRestore }: VersionCardProps) {
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-border p-card">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-accent/10 px-1.5 py-0.5 text-xs font-medium text-accent">
            v{v.version}
          </span>
          <span className="text-sm text-foreground">{v.snapshot.name}</span>
        </div>
        {v.version === definition?.version && (
          <span className="text-xs text-success">Current</span>
        )}
      </div>

      <div className="flex items-center gap-2 text-xs text-muted">
        <Clock className="size-3" aria-hidden="true" />
        <time dateTime={v.saved_at}>{formatRelativeTime(v.saved_at)}</time>
        <span>by {v.saved_by}</span>
      </div>

      <div className="flex gap-1 pt-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onCompare(v)}
          disabled={v.version === definition?.version}
          title="Compare with current"
        >
          <GitCompare className="size-3.5" />
          <span className="ml-1">Compare</span>
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onRestore(v.version)}
          disabled={v.version === definition?.version || saving}
          title="Restore this version"
        >
          <RotateCcw className="size-3.5" />
          <span className="ml-1">Restore</span>
        </Button>
      </div>
    </div>
  )
}

interface VersionHistoryPanelProps {
  open: boolean
  onClose: () => void
}

export function VersionHistoryPanel({ open, onClose }: VersionHistoryPanelProps) {
  const versions = useWorkflowEditorStore((s) => s.versions)
  const versionsLoading = useWorkflowEditorStore((s) => s.versionsLoading)
  const versionsHasMore = useWorkflowEditorStore((s) => s.versionsHasMore)
  const definition = useWorkflowEditorStore((s) => s.definition)
  const loadDiff = useWorkflowEditorStore((s) => s.loadDiff)
  const rollback = useWorkflowEditorStore((s) => s.rollback)
  const loadMoreVersions = useWorkflowEditorStore((s) => s.loadMoreVersions)
  const saving = useWorkflowEditorStore((s) => s.saving)

  const [restoreTarget, setRestoreTarget] = useState<number | null>(null)

  function handleCompare(version: WorkflowDefinitionVersionSummary) {
    if (!definition) return
    loadDiff(version.version, definition.version)
  }

  function handleRestore(version: number) {
    setRestoreTarget(version)
  }

  async function confirmRestore() {
    if (restoreTarget === null) return
    await rollback(restoreTarget)
    setRestoreTarget(null)
  }

  return (
    <>
      <Drawer
        open={open}
        onClose={onClose}
        title="Version History"
        side="right"
      >
        <div className="flex flex-col gap-section-gap">
          {versionsLoading && versions.length === 0 && (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 3 }, (_, i) => (
                <Skeleton key={i} className="h-16 rounded-lg" />
              ))}
            </div>
          )}

          {!versionsLoading && versions.length === 0 && (
            <p className="py-4 text-center text-sm text-muted">
              No version history yet
            </p>
          )}

          {versions.map((v) => (
            <VersionCard
              key={v.version}
              v={v}
              definition={definition}
              saving={saving}
              onCompare={handleCompare}
              onRestore={handleRestore}
            />
          ))}

          {versionsHasMore && (
            <Button
              variant="ghost"
              size="sm"
              onClick={loadMoreVersions}
              disabled={versionsLoading}
              className="self-center"
            >
              {versionsLoading ? 'Loading...' : 'Load more'}
            </Button>
          )}
        </div>
      </Drawer>

      <ConfirmDialog
        open={restoreTarget !== null}
        onOpenChange={(open) => { if (!open) setRestoreTarget(null) }}
        onConfirm={confirmRestore}
        title="Restore Version"
        description={`Restore to version ${restoreTarget}? This creates a new version with the old content -- no history is lost.`}
        confirmLabel="Restore"
        loading={saving}
      />
    </>
  )
}
