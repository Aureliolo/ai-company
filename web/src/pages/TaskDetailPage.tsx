import { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { InlineEdit } from '@/components/ui/inline-edit'
import { TaskStatusIndicator } from '@/components/ui/task-status-indicator'
import { PriorityBadge } from '@/components/ui/task-status-indicator'
import { Avatar } from '@/components/ui/avatar'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useTasksStore } from '@/stores/tasks'
import { useToastStore } from '@/stores/toast'
import { getTaskStatusLabel, getTaskTypeLabel, getAvailableTransitions, getPriorityLabel } from '@/utils/tasks'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import { formatDate, formatCurrency } from '@/utils/format'
import { getErrorMessage } from '@/utils/errors'
import { ROUTES } from '@/router/routes'
import type { Priority, TaskStatus, WsEvent } from '@/api/types'

const PRIORITIES: Priority[] = ['critical', 'high', 'medium', 'low']

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const selectedTask = useTasksStore((s) => s.selectedTask)
  const loadingDetail = useTasksStore((s) => s.loadingDetail)
  const error = useTasksStore((s) => s.error)

  const [deleteOpen, setDeleteOpen] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [transitioning, setTransitioning] = useState<TaskStatus | null>(null)

  // Subscribe to real-time task updates via WebSocket
  const wsBindings = useMemo(() => [{
    channel: 'tasks' as const,
    handler: (event: WsEvent) => {
      useTasksStore.getState().handleWsEvent(event)
    },
  }], [])
  const { setupError: wsSetupError } = useWebSocket({ bindings: wsBindings })

  useEffect(() => {
    if (taskId) {
      useTasksStore.getState().fetchTask(taskId)
    }
  }, [taskId])

  const task = selectedTask?.id === taskId ? selectedTask : undefined

  const handleTransition = useCallback(async (targetStatus: TaskStatus) => {
    if (!task) return
    setTransitioning(targetStatus)
    try {
      await useTasksStore.getState().transitionTask(task.id, {
        target_status: targetStatus,
        expected_version: task.version,
      })
      useToastStore.getState().add({ variant: 'success', title: `Task moved to ${getTaskStatusLabel(targetStatus)}` })
    } catch {
      useToastStore.getState().add({ variant: 'error', title: 'Transition failed' })
    } finally {
      setTransitioning(null)
    }
  }, [task])

  const handleDelete = useCallback(async () => {
    if (!task) return
    try {
      await useTasksStore.getState().deleteTask(task.id)
      setDeleteOpen(false)
      navigate(ROUTES.TASKS)
    } catch {
      useToastStore.getState().add({ variant: 'error', title: 'Failed to delete task' })
    }
  }, [task, navigate])

  const handleCancel = useCallback(async () => {
    if (!task) return
    if (!cancelReason.trim()) {
      useToastStore.getState().add({ variant: 'error', title: 'Please provide a cancellation reason' })
      return
    }
    try {
      await useTasksStore.getState().cancelTask(task.id, { reason: cancelReason.trim() })
      setCancelOpen(false)
      setCancelReason('')
    } catch {
      useToastStore.getState().add({ variant: 'error', title: 'Failed to cancel task' })
    }
  }, [task, cancelReason])

  if (error && !task) {
    return (
      <div className="py-20 text-center text-sm text-danger">
        {error}
      </div>
    )
  }

  if (loadingDetail || !task) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="size-8 animate-spin text-text-muted" />
      </div>
    )
  }

  const availableTransitions = getAvailableTransitions(task.status)

  return (
    <div className="mx-auto max-w-3xl space-y-section-gap">
      <Button variant="ghost" size="sm" onClick={() => navigate(ROUTES.TASKS)}>
        <ArrowLeft className="mr-1 size-4" />
        Back to Board
      </Button>

      {wsSetupError && (
        <div className="rounded-md border border-warning/30 bg-warning/10 p-card text-sm text-warning">
          Real-time updates unavailable: {wsSetupError}
        </div>
      )}

      <ErrorBoundary level="section">
        <div className="rounded-lg border border-border bg-card p-6 space-y-6">
          {/* Header */}
          <div className="flex items-start justify-between">
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-2">
                <TaskStatusIndicator status={task.status} label />
                <PriorityBadge priority={task.priority} />
              </div>
              <InlineEdit
                value={task.title}
                onSave={async (value) => {
                  try {
                    await useTasksStore.getState().updateTask(task.id, { title: value, expected_version: task.version })
                  } catch (err) {
                    useToastStore.getState().add({ variant: 'error', title: 'Failed to save title', description: getErrorMessage(err) })
                    throw err
                  }
                }}
                validate={(v) => v.trim().length === 0 ? 'Title is required' : null}
                className="text-xl font-semibold"
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">Description</label>
            <InlineEdit
              value={task.description}
              onSave={async (value) => {
                try {
                  await useTasksStore.getState().updateTask(task.id, { description: value, expected_version: task.version })
                } catch (err) {
                  useToastStore.getState().add({ variant: 'error', title: 'Failed to save description', description: getErrorMessage(err) })
                  throw err
                }
              }}
              className="mt-1 text-sm text-text-secondary"
            />
          </div>

          {/* Priority selector */}
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">Priority</label>
            <div className="mt-1">
              <select
                value={task.priority}
                onChange={async (e) => {
                  try {
                    await useTasksStore.getState().updateTask(task.id, { priority: e.target.value as Priority, expected_version: task.version })
                  } catch (err) {
                    useToastStore.getState().add({ variant: 'error', title: 'Failed to update priority', description: getErrorMessage(err) })
                  }
                }}
                className="h-8 rounded-md border border-border bg-surface px-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>{getPriorityLabel(p)}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Assignee */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">Assignee:</span>
            {task.assigned_to ? (
              <span className="flex items-center gap-1.5">
                <Avatar name={task.assigned_to} size="sm" />
                <span className="text-sm text-foreground">{task.assigned_to}</span>
              </span>
            ) : (
              <span className="text-sm text-text-muted">Unassigned</span>
            )}
          </div>

          {/* Metadata */}
          <div className="grid grid-cols-3 gap-grid-gap rounded-lg border border-border p-card text-sm">
            <div><span className="block text-[10px] text-text-muted">Type</span><span className="text-foreground">{getTaskTypeLabel(task.type)}</span></div>
            <div><span className="block text-[10px] text-text-muted">Complexity</span><span className="capitalize text-foreground">{task.estimated_complexity}</span></div>
            <div><span className="block text-[10px] text-text-muted">Project</span><span className="text-foreground">{task.project}</span></div>
            <div><span className="block text-[10px] text-text-muted">Created</span><span className="font-mono text-xs text-foreground">{formatDate(task.created_at)}</span></div>
            <div><span className="block text-[10px] text-text-muted">Updated</span><span className="font-mono text-xs text-foreground">{formatDate(task.updated_at)}</span></div>
            {task.cost != null && (
              <div><span className="block text-[10px] text-text-muted">Cost</span><span className="font-mono text-xs text-foreground">{formatCurrency(task.cost, DEFAULT_CURRENCY)}</span></div>
            )}
          </div>

          {/* Dependencies */}
          {task.dependencies.length > 0 && (
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Dependencies ({task.dependencies.length})
              </span>
              <ul className="mt-1.5 space-y-1">
                {task.dependencies.map((depId) => (
                  <li key={depId} className="rounded border border-border px-2 py-1 font-mono text-xs text-text-secondary">
                    {depId}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Acceptance criteria */}
          {task.acceptance_criteria.length > 0 && (
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Acceptance Criteria
              </span>
              <ul className="mt-1.5 space-y-1">
                {task.acceptance_criteria.map((criterion, idx) => (
                  // eslint-disable-next-line @eslint-react/no-array-index-key -- criteria lack unique IDs; descriptions may duplicate
                  <li key={`${criterion.description}-${idx}`} className="flex items-start gap-2 text-sm text-text-secondary">
                    <span className={cn('mt-0.5 size-4 shrink-0 rounded border', criterion.met ? 'border-success bg-success/20' : 'border-border')} />
                    {criterion.description}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Transitions */}
          {availableTransitions.length > 0 && (
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Transitions
              </span>
              <div className="mt-1.5 flex flex-wrap gap-2">
                {availableTransitions.map((targetStatus) => (
                  <Button
                    key={targetStatus}
                    size="sm"
                    variant="outline"
                    disabled={transitioning !== null}
                    onClick={() => handleTransition(targetStatus)}
                  >
                    {transitioning === targetStatus && <Loader2 className="mr-1 size-3 animate-spin" />}
                    {getTaskStatusLabel(targetStatus)}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
            {task.status !== 'cancelled' && task.status !== 'completed' && (
              <Button variant="outline" size="sm" onClick={() => setCancelOpen(true)}>
                Cancel Task
              </Button>
            )}
            <Button variant="destructive" size="sm" onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          </div>
        </div>
      </ErrorBoundary>

      <ConfirmDialog
        open={cancelOpen}
        onOpenChange={(open) => { setCancelOpen(open); if (!open) setCancelReason('') }}
        title="Cancel Task"
        description="Are you sure? Please provide a reason for cancellation."
        confirmLabel="Cancel Task"
        variant="destructive"
        onConfirm={handleCancel}
      >
        <textarea
          value={cancelReason}
          onChange={(e) => setCancelReason(e.target.value)}
          placeholder="Reason for cancellation..."
          className="mt-2 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-foreground outline-none resize-y focus:ring-2 focus:ring-accent min-h-[60px]"
          aria-label="Cancellation reason"
        />
      </ConfirmDialog>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Task"
        description="This action cannot be undone. The task will be permanently deleted."
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={handleDelete}
      />
    </div>
  )
}
