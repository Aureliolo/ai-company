import { Link, useNavigate } from 'react-router'
import { DropdownMenu } from 'radix-ui'
import { MoreHorizontal, Pencil, Copy, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { ROUTES } from '@/router/routes'
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
  const [confirmDelete, setConfirmDelete] = useState(false)
  const navigate = useNavigate()

  const editorUrl = `${ROUTES.WORKFLOW_EDITOR}?id=${encodeURIComponent(workflow.id)}`

  return (
    <>
      <div className="relative rounded-lg border border-border bg-card p-card transition-shadow hover:shadow-[var(--so-shadow-card-hover)]">
        <Link to={editorUrl} className="block">
          <div className="mb-2 flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-foreground">
              {workflow.name}
            </span>
            <span className="rounded-md bg-accent/10 px-1.5 py-0.5 text-xs font-medium text-accent">
              {formatLabel(workflow.workflow_type)}
            </span>
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

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>v{workflow.version}</span>
            <span>Updated {formatRelativeTime(workflow.updated_at)}</span>
          </div>
        </Link>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
              }}
              className="absolute right-3 top-3 rounded p-1 text-muted-foreground hover:bg-surface hover:text-foreground"
              aria-label="Workflow actions"
            >
              <MoreHorizontal className="size-4" />
            </button>
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={4}
              className="z-50 w-36 rounded-lg border border-border bg-card py-1 shadow-lg"
            >
              <DropdownMenu.Item
                className="flex w-full cursor-default items-center gap-2 px-3 py-1.5 text-sm text-foreground outline-none hover:bg-surface focus:bg-surface"
                onSelect={() => { void navigate(editorUrl) }}
              >
                <Pencil className="size-3.5" />
                Edit
              </DropdownMenu.Item>
              <DropdownMenu.Item
                className="flex w-full cursor-default items-center gap-2 px-3 py-1.5 text-sm text-foreground outline-none hover:bg-surface focus:bg-surface"
                onSelect={() => { onDuplicate(workflow.id) }}
              >
                <Copy className="size-3.5" />
                Duplicate
              </DropdownMenu.Item>
              <DropdownMenu.Item
                className="flex w-full cursor-default items-center gap-2 px-3 py-1.5 text-sm text-danger outline-none hover:bg-surface focus:bg-surface"
                onSelect={() => { setConfirmDelete(true) }}
              >
                <Trash2 className="size-3.5" />
                Delete
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={(open) => { if (!open) setConfirmDelete(false) }}
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
