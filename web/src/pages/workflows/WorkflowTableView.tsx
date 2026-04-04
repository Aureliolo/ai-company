import { useNavigate } from 'react-router'
import { Workflow, MoreHorizontal, Copy, Trash2, Pencil } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useState } from 'react'
import { ROUTES } from '@/router/routes'
import { EmptyState } from '@/components/ui/empty-state'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import type { WorkflowDefinition } from '@/api/types'

interface WorkflowTableViewProps {
  workflows: readonly WorkflowDefinition[]
  onDelete: (id: string) => void
  onDuplicate: (id: string) => void
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function WorkflowTableView({ workflows, onDelete, onDuplicate }: WorkflowTableViewProps) {
  const navigate = useNavigate()
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  if (workflows.length === 0) {
    return (
      <EmptyState
        icon={Workflow}
        title="No workflows found"
        description="Try adjusting your filters or create a new workflow."
      />
    )
  }

  return (
    <>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm" role="table">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="px-4 py-2 text-left font-medium text-muted-foreground">Name</th>
              <th className="px-4 py-2 text-left font-medium text-muted-foreground">Type</th>
              <th className="px-4 py-2 text-right font-medium text-muted-foreground">Nodes</th>
              <th className="px-4 py-2 text-right font-medium text-muted-foreground">Edges</th>
              <th className="px-4 py-2 text-right font-medium text-muted-foreground">Version</th>
              <th className="px-4 py-2 text-left font-medium text-muted-foreground">Updated</th>
              <th className="w-10 px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {workflows.map((w) => {
              const editorUrl = `${ROUTES.WORKFLOW_EDITOR}?id=${encodeURIComponent(w.id)}`
              return (
                <tr
                  key={w.id}
                  tabIndex={0}
                  className="cursor-pointer border-b border-border last:border-0 transition-colors hover:bg-muted/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                  onClick={() => navigate(editorUrl)}
                  onKeyDown={(e) => {
                    if (e.key !== 'Enter' && e.key !== ' ') return
                    const target = e.target as HTMLElement
                    if (target.closest('button, a, input, select, textarea, [role="menuitem"]')) return
                    e.preventDefault()
                    navigate(editorUrl)
                  }}
                  role="link"
                  aria-label={`Open workflow ${w.name}`}
                >
                  <td className="px-4 py-2.5 font-medium text-foreground">{w.name}</td>
                  <td className="px-4 py-2.5">
                    <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
                      {w.workflow_type.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right text-muted-foreground">{w.nodes.length}</td>
                  <td className="px-4 py-2.5 text-right text-muted-foreground">{w.edges.length}</td>
                  <td className="px-4 py-2.5 text-right text-muted-foreground">v{w.version}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{formatDate(w.updated_at)}</td>
                  <td className="px-2 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu.Root>
                      <DropdownMenu.Trigger asChild>
                        <button
                          type="button"
                          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                          aria-label={`Actions for ${w.name}`}
                        >
                          <MoreHorizontal className="size-4" />
                        </button>
                      </DropdownMenu.Trigger>
                      <DropdownMenu.Portal>
                        <DropdownMenu.Content
                          align="end"
                          sideOffset={4}
                          className="z-50 min-w-36 rounded-md border border-border bg-popover p-1 shadow-[var(--so-shadow-card-hover)]"
                        >
                          <DropdownMenu.Item
                            className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-foreground outline-none hover:bg-accent/10 focus:bg-accent/10"
                            onSelect={() => navigate(editorUrl)}
                          >
                            <Pencil className="size-3.5" />
                            Edit
                          </DropdownMenu.Item>
                          <DropdownMenu.Item
                            className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-foreground outline-none hover:bg-accent/10 focus:bg-accent/10"
                            onSelect={() => onDuplicate(w.id)}
                          >
                            <Copy className="size-3.5" />
                            Duplicate
                          </DropdownMenu.Item>
                          <DropdownMenu.Item
                            className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-danger outline-none hover:bg-danger/10 focus:bg-danger/10"
                            onSelect={() => setConfirmDeleteId(w.id)}
                          >
                            <Trash2 className="size-3.5" />
                            Delete
                          </DropdownMenu.Item>
                        </DropdownMenu.Content>
                      </DropdownMenu.Portal>
                    </DropdownMenu.Root>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={confirmDeleteId !== null}
        onOpenChange={(open) => { if (!open) setConfirmDeleteId(null) }}
        onConfirm={() => {
          if (confirmDeleteId) onDelete(confirmDeleteId)
          setConfirmDeleteId(null)
        }}
        title="Delete workflow"
        description="This action cannot be undone. The workflow definition will be permanently deleted."
        variant="destructive"
        confirmLabel="Delete"
      />
    </>
  )
}
