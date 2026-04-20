import { useState } from 'react'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { InputField } from '@/components/ui/input-field'

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
      <div className="mt-2">
        <InputField
          multiline
          label="Cancellation reason"
          value={reason}
          onValueChange={setReason}
          placeholder="Reason for cancellation..."
          rows={3}
        />
      </div>
    </ConfirmDialog>
  )
}
