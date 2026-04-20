import { useState } from 'react'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

interface TaskCancelDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (reason: string) => Promise<boolean>
}

export function TaskCancelDialog({ open, onOpenChange, onConfirm }: TaskCancelDialogProps) {
  const [reason, setReason] = useState('')

  const handleOpenChange = (next: boolean) => {
    onOpenChange(next)
    if (!next) setReason('')
  }

  const handleConfirm = async () => {
    const ok = await onConfirm(reason)
    if (ok) {
      handleOpenChange(false)
    }
  }

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Cancel Task"
      description="Are you sure? Please provide a reason for cancellation."
      confirmLabel="Cancel Task"
      variant="destructive"
      onConfirm={handleConfirm}
    >
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Reason for cancellation..."
        className="mt-2 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-foreground outline-none resize-y focus:ring-2 focus:ring-accent min-h-[60px]"
        aria-label="Cancellation reason"
      />
    </ConfirmDialog>
  )
}
