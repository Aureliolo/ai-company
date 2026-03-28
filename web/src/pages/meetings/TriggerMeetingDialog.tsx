import { useState } from 'react'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { InputField } from '@/components/ui/input-field'

interface TriggerMeetingDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (eventName: string) => Promise<void>
  loading?: boolean
}

export function TriggerMeetingDialog({
  open,
  onOpenChange,
  onConfirm,
  loading,
}: TriggerMeetingDialogProps) {
  const [eventName, setEventName] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  const handleConfirm = async () => {
    const trimmed = eventName.trim()
    if (!trimmed) {
      setValidationError('Event name is required.')
      return
    }
    setValidationError(null)
    await onConfirm(trimmed)
    setEventName('')
  }

  const handleOpenChange = (o: boolean) => {
    onOpenChange(o)
    if (!o) {
      setEventName('')
      setValidationError(null)
    }
  }

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Trigger Meeting"
      description="Enter the event name to trigger an event-based meeting."
      confirmLabel="Trigger"
      onConfirm={handleConfirm}
      loading={loading}
    >
      <div className="mt-3">
        <InputField
          label="Event Name"
          value={eventName}
          onChange={(e) => { setEventName(e.target.value); setValidationError(null) }}
          placeholder="e.g. on_pr, deploy_complete"
          error={validationError}
          required
        />
      </div>
    </ConfirmDialog>
  )
}
