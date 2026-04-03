import { Link } from 'react-router'
import { MoreHorizontal, Pencil, Copy, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { ROUTES } from '@/router/routes'
import { StatusBadge } from '@/components/ui/status-badge'
import { StatPill } from '@/components/ui/stat-pill'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { formatRelativeTime, formatLabel } from '@/utils/format'
import type { WorkflowDefinition } from '@/api/types'

interface WorkflowCardProps {
  workflow: WorkflowDefinition
  onDelete: (id: string) => void
  onDuplicate: (id: string) => void
}

export function WorkflowCard({ workflow, onDelete, onDuplicate }: WorkflowCardProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const editorUrl = `${ROUTES.WORKFLOW_EDITOR}?id=${encodeURIComponent(workflow.id)}`

  return (
    <>
      <div className="relative rounded-lg border border-border bg-card p-card transition-shadow hover:shadow-[var(--so-shadow-card-hover)]">
        <Link to={editorUrl} className="block">
          <div className="mb-2 flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-foreground">
              {workflow.name}
            </span>
            <StatusBadge status="info" label={formatLabel(workflow.workflow_type)} />
          </div>

          {workflow.description && (
            <p className="mb-3 line-clamp-2 text-xs text-muted-foreground">
              {workflow.description}
            </p>
          )}

          <div className="mb-2 flex flex-wrap items-center gap-2">
            <StatPill label="Nodes" value={workflow.nodes.length} />
            <StatPill label="Edges" value={workflow.edges.length} />
          </div>

          <div className="flex items-center justify-between text-xs text-text-muted">
            <span>v{workflow.version}</span>
            <span>Updated {formatRelativeTime(workflow.updated_at)}</span>
          </div>
        </Link>

        <div className="absolute right-3 top-3">
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              setMenuOpen(!menuOpen)
            }}
            className="rounded p-1 text-muted-foreground hover:bg-surface hover:text-foreground"
            aria-label="Workflow actions"
          >
            <MoreHorizontal className="size-4" />
          </button>

          {menuOpen && (
            <div
              className="absolute right-0 top-full z-10 mt-1 w-36 rounded-lg border border-border bg-card py-1 shadow-lg"
              role="menu"
            >
              <Link
                to={editorUrl}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-foreground hover:bg-surface"
                role="menuitem"
                onClick={() => setMenuOpen(false)}
              >
                <Pencil className="size-3.5" />
                Edit
              </Link>
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-foreground hover:bg-surface"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false)
                  onDuplicate(workflow.id)
                }}
              >
                <Copy className="size-3.5" />
                Duplicate
              </button>
              <button
                type="button"
                className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-danger hover:bg-surface"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false)
                  setConfirmDelete(true)
                }}
              >
                <Trash2 className="size-3.5" />
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => {
          onDelete(workflow.id)
          setConfirmDelete(false)
        }}
        title="Delete workflow"
        description={`Are you sure you want to delete "${workflow.name}"? This action cannot be undone.`}
        variant="destructive"
        confirmLabel="Delete"
      />
    </>
  )
}
