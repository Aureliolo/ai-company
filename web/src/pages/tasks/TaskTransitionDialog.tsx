import type { TaskStatus } from '@/api/types/enums'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { getTaskStatusLabel } from '@/utils/tasks'

interface TaskTransitionDialogProps {
  open: boolean
  targetStatus: TaskStatus | null
  transitioning: TaskStatus | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

/**
 * Confirmation dialog for task state transitions that are destructive or
 * terminal (completed, rejected, failed). For low-risk transitions the
 * caller should invoke the transition directly and skip this dialog.
 */
export function TaskTransitionDialog({
  open,
  targetStatus,
  transitioning,
  onOpenChange,
  onConfirm,
}: TaskTransitionDialogProps) {
  if (!targetStatus) return null

  const isDestructive = targetStatus === 'rejected' || targetStatus === 'failed'
  const label = getTaskStatusLabel(targetStatus)

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Move task to ${label}?`}
      description={
        isDestructive
          ? `This marks the task as ${label.toLowerCase()}. The transition cannot be undone.`
          : `Mark this task as ${label.toLowerCase()}?`
      }
      confirmLabel={`Move to ${label}`}
      variant={isDestructive ? 'destructive' : 'default'}
      loading={transitioning === targetStatus}
      onConfirm={onConfirm}
    />
  )
}
