import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { ArrowLeft, Loader2 } from 'lucide-react'
import type { TaskStatus } from '@/api/types/enums'
import { Button } from '@/components/ui/button'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { useTasksStore } from '@/stores/tasks'
import { ROUTES } from '@/router/routes'
import { TaskCancelDialog } from './tasks/TaskCancelDialog'
import { TaskDeleteDialog } from './tasks/TaskDeleteDialog'
import { TaskDetailActions } from './tasks/TaskDetailActions'
import { TaskDetailHeader } from './tasks/TaskDetailHeader'
import { TaskDetailMetadata } from './tasks/TaskDetailMetadata'
import { TaskDetailTimeline } from './tasks/TaskDetailTimeline'
import { TaskTransitionDialog } from './tasks/TaskTransitionDialog'
import { requiresTransitionConfirmation } from './tasks/transition-confirmation'
import { useTaskActionHandlers } from './tasks/useTaskActionHandlers'
import { useTaskWebSocketUpdates } from './tasks/useTaskWebSocketUpdates'

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const selectedTask = useTasksStore((s) => s.selectedTask)
  const loadingDetail = useTasksStore((s) => s.loadingDetail)
  const error = useTasksStore((s) => s.error)

  const [deleteOpen, setDeleteOpen] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [pendingTransition, setPendingTransition] = useState<TaskStatus | null>(null)

  const { setupError: wsSetupError } = useTaskWebSocketUpdates()

  useEffect(() => {
    if (taskId) {
      useTasksStore.getState().fetchTask(taskId)
    }
  }, [taskId])

  const task = selectedTask?.id === taskId ? selectedTask : undefined
  const { transitioning, transitionTo, deleteTask, cancelTask } = useTaskActionHandlers(task)

  const handleTransitionRequest = useCallback(
    (target: TaskStatus) => {
      if (requiresTransitionConfirmation(target)) {
        setPendingTransition(target)
      } else {
        void transitionTo(target)
      }
    },
    [transitionTo],
  )

  const handleTransitionConfirm = useCallback(async () => {
    if (!pendingTransition) return
    const target = pendingTransition
    await transitionTo(target)
    setPendingTransition(null)
  }, [pendingTransition, transitionTo])

  if (error && !task) {
    return <div className="py-20 text-center text-sm text-danger">{error}</div>
  }

  if (loadingDetail || !task) {
    return (
      <div
        className="flex items-center justify-center py-20"
        role="status"
        aria-label="Loading task"
      >
        <Loader2 className="size-8 animate-spin text-text-muted" />
      </div>
    )
  }

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
        <div className="rounded-lg border border-border bg-card p-6 space-y-section-gap">
          <TaskDetailHeader task={task} />
          <TaskDetailMetadata task={task} />
          <TaskDetailTimeline task={task} />
          <TaskDetailActions
            task={task}
            transitioning={transitioning}
            onTransition={handleTransitionRequest}
            onRequestCancel={() => setCancelOpen(true)}
            onRequestDelete={() => setDeleteOpen(true)}
          />
        </div>
      </ErrorBoundary>

      <TaskCancelDialog open={cancelOpen} onOpenChange={setCancelOpen} onConfirm={cancelTask} />
      <TaskDeleteDialog open={deleteOpen} onOpenChange={setDeleteOpen} onConfirm={deleteTask} />
      <TaskTransitionDialog
        open={pendingTransition !== null}
        targetStatus={pendingTransition}
        transitioning={transitioning}
        onOpenChange={(next) => {
          if (!next) setPendingTransition(null)
        }}
        onConfirm={handleTransitionConfirm}
      />
    </div>
  )
}
