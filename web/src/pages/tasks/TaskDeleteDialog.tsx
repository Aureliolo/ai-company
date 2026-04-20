import { ConfirmDialog } from '@/components/ui/confirm-dialog'

interface TaskDeleteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => Promise<void> | void
}

export function TaskDeleteDialog({ open, onOpenChange, onConfirm }: TaskDeleteDialogProps) {
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Delete Task"
      description="This action cannot be undone. The task will be permanently deleted."
      confirmLabel="Delete"
      variant="destructive"
      onConfirm={onConfirm}
    />
  )
}
