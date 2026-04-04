import { Clock, GitCompare, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Drawer } from '@/components/ui/drawer'
import { Skeleton } from '@/components/ui/skeleton'
import { useWorkflowEditorStore } from '@/stores/workflow-editor'
import { useState } from 'react'
import { formatRelativeTime } from '@/utils/format'
import type { WorkflowDefinitionVersionSummary } from '@/api/types'

interface VersionHistoryPanelProps {
  open: boolean
  onClose: () => void
}

export function VersionHistoryPanel({ open, onClose }: VersionHistoryPanelProps) {
  const versions = useWorkflowEditorStore((s) => s.versions)
  const versionsLoading = useWorkflowEditorStore((s) => s.versionsLoading)
  const definition = useWorkflowEditorStore((s) => s.definition)
  const loadDiff = useWorkflowEditorStore((s) => s.loadDiff)
  const rollback = useWorkflowEditorStore((s) => s.rollback)
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
        <div className="flex flex-col gap-3">
          {versionsLoading && (
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

          {!versionsLoading &&
            versions.map((v) => (
              <div
                key={v.version}
                className="flex flex-col gap-1.5 rounded-lg border border-border p-card"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="rounded-md bg-accent/10 px-1.5 py-0.5 text-xs font-medium text-accent">
                      v{v.version}
                    </span>
                    <span className="text-sm text-foreground">{v.name}</span>
                  </div>
                  {v.version === definition?.version && (
                    <span className="text-xs text-success">Current</span>
                  )}
                </div>

                <div className="flex items-center gap-2 text-xs text-muted">
                  <Clock className="size-3" />
                  <span>{formatRelativeTime(v.saved_at)}</span>
                  <span>by {v.saved_by}</span>
                </div>

                <div className="flex gap-1 pt-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleCompare(v)}
                    disabled={v.version === definition?.version}
                    title="Compare with current"
                  >
                    <GitCompare className="size-3.5" />
                    <span className="ml-1">Compare</span>
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRestore(v.version)}
                    disabled={
                      v.version === definition?.version || saving
                    }
                    title="Restore this version"
                  >
                    <RotateCcw className="size-3.5" />
                    <span className="ml-1">Restore</span>
                  </Button>
                </div>
              </div>
            ))}
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
