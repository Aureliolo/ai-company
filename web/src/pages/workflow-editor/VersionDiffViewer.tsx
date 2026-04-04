import { X, Plus, Minus, Move, Settings, Tag, Shuffle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useWorkflowEditorStore } from '@/stores/workflow-editor'
import { cn } from '@/lib/utils'
import type { NodeChange as NodeChangeType, EdgeChange as EdgeChangeType } from '@/api/types'

const NODE_CHANGE_ICONS: Record<string, typeof Plus> = {
  added: Plus,
  removed: Minus,
  moved: Move,
  config_changed: Settings,
  label_changed: Tag,
  type_changed: Shuffle,
}

const NODE_CHANGE_COLORS: Record<string, string> = {
  added: 'text-success',
  removed: 'text-danger',
  moved: 'text-accent',
  config_changed: 'text-warning',
  label_changed: 'text-muted',
  type_changed: 'text-warning',
}

const EDGE_CHANGE_COLORS: Record<string, string> = {
  added: 'text-success',
  removed: 'text-danger',
  reconnected: 'text-accent',
  type_changed: 'text-warning',
  label_changed: 'text-muted',
}

export function VersionDiffViewer() {
  const diffResult = useWorkflowEditorStore((s) => s.diffResult)
  const clearDiff = useWorkflowEditorStore((s) => s.clearDiff)

  if (!diffResult) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="relative mx-4 flex max-h-[80vh] w-full max-w-2xl flex-col rounded-xl border border-border bg-background shadow-lg">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              Version Diff
            </h2>
            <p className="text-sm text-muted">
              v{diffResult.from_version} to v{diffResult.to_version}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={clearDiff}>
            <X className="size-4" />
          </Button>
        </div>

        {/* Summary */}
        <div className="border-b border-border px-6 py-3">
          <p className="text-sm text-muted">{diffResult.summary}</p>
        </div>

        {/* Changes list */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* Metadata changes */}
          {diffResult.metadata_changes.length > 0 && (
            <section className="mb-4">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                Metadata
              </h3>
              <div className="flex flex-col gap-1">
                {diffResult.metadata_changes.map((mc) => (
                  <div
                    key={mc.field}
                    className="rounded-md bg-card p-2 text-sm"
                  >
                    <span className="font-medium text-foreground">
                      {mc.field}
                    </span>
                    :{' '}
                    <span className="text-danger line-through">
                      {mc.old_value}
                    </span>{' '}
                    <span className="text-success">{mc.new_value}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Node changes */}
          {diffResult.node_changes.length > 0 && (
            <section className="mb-4">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                Node Changes
              </h3>
              <div className="flex flex-col gap-1">
                {diffResult.node_changes.map((nc) => (
                  <NodeChangeRow key={`${nc.node_id}-${nc.change_type}`} change={nc} />
                ))}
              </div>
            </section>
          )}

          {/* Edge changes */}
          {diffResult.edge_changes.length > 0 && (
            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                Edge Changes
              </h3>
              <div className="flex flex-col gap-1">
                {diffResult.edge_changes.map((ec) => (
                  <EdgeChangeRow key={`${ec.edge_id}-${ec.change_type}`} change={ec} />
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}

function NodeChangeRow({ change }: { change: NodeChangeType }) {
  const Icon = NODE_CHANGE_ICONS[change.change_type] ?? Settings
  const color = NODE_CHANGE_COLORS[change.change_type] ?? 'text-muted'
  const label = change.change_type.replace(/_/g, ' ')

  return (
    <div className="flex items-center gap-2 rounded-md bg-card p-2 text-sm">
      <Icon className={cn('size-3.5', color)} />
      <span className="font-medium text-foreground">{change.node_id}</span>
      <span className={cn('text-xs', color)}>{label}</span>
    </div>
  )
}

function EdgeChangeRow({ change }: { change: EdgeChangeType }) {
  const color = EDGE_CHANGE_COLORS[change.change_type] ?? 'text-muted'
  const label = change.change_type.replace(/_/g, ' ')

  return (
    <div className="flex items-center gap-2 rounded-md bg-card p-2 text-sm">
      <span className="font-medium text-foreground">{change.edge_id}</span>
      <span className={cn('text-xs', color)}>{label}</span>
    </div>
  )
}
