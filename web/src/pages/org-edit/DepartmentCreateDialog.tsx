import { useCallback, useEffect, useState } from 'react'
import { Dialog } from 'radix-ui'
import { Loader2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { getErrorMessage } from '@/utils/errors'
import type { CreateDepartmentRequest, Department } from '@/api/types'

export interface DepartmentCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  existingNames: readonly string[]
  onCreate: (data: CreateDepartmentRequest) => Promise<Department>
  disabled?: boolean
}

interface FormState {
  name: string
  display_name: string
  budget_percent: string
}

const INITIAL_FORM: FormState = {
  name: '',
  display_name: '',
  budget_percent: '0',
}

export function DepartmentCreateDialog({ open, onOpenChange, existingNames, onCreate, disabled }: DepartmentCreateDialogProps) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM)
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      setForm(INITIAL_FORM)
      setErrors({})
      setSubmitError(null)
    }
  }, [open])

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
    setSubmitError(null)
  }

  const handleSubmit = useCallback(async () => {
    const next: Partial<Record<keyof FormState, string>> = {}
    if (!form.name.trim()) {
      next.name = 'Name is required'
    } else if (existingNames.some((n) => n.toLowerCase() === form.name.trim().toLowerCase())) {
      next.name = 'Department already exists'
    }
    if (!form.display_name.trim()) next.display_name = 'Display name is required'
    const pct = Number(form.budget_percent)
    if (!Number.isFinite(pct) || pct < 0 || pct > 100) {
      next.budget_percent = 'Must be between 0 and 100'
    }
    setErrors(next)
    if (Object.keys(next).length > 0) return

    setSubmitting(true)
    setSubmitError(null)
    try {
      await onCreate({
        name: form.name.trim(),
        display_name: form.display_name.trim(),
        budget_percent: Number(form.budget_percent),
      })
      setForm(INITIAL_FORM)
      onOpenChange(false)
    } catch (err) {
      setSubmitError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }, [form, existingNames, onCreate, onOpenChange])

  return (
    <Dialog.Root open={open} onOpenChange={(v) => { if (!submitting) onOpenChange(v) }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            'fixed top-1/2 left-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2',
            'rounded-xl border border-border-bright bg-surface p-6 shadow-lg',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
          )}
        >
          <div className="flex items-center justify-between mb-4">
            <Dialog.Title className="text-base font-semibold text-foreground">
              New Department
            </Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Close">
                <X className="size-4" />
              </Button>
            </Dialog.Close>
          </div>

          <div className="space-y-4">
            <InputField
              label="Name"
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              error={errors.name}
              required
              autoFocus
              placeholder="e.g. engineering"
            />

            <InputField
              label="Display Name"
              value={form.display_name}
              onChange={(e) => updateField('display_name', e.target.value)}
              error={errors.display_name}
              required
              placeholder="e.g. Engineering"
            />

            <InputField
              label="Budget %"
              type="number"
              value={form.budget_percent}
              onChange={(e) => updateField('budget_percent', e.target.value)}
              error={errors.budget_percent}
              hint="Percentage of company budget (0-100)"
            />

            {submitError && (
              <p className="text-xs text-danger">{submitError}</p>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Dialog.Close asChild>
                <Button variant="outline" disabled={submitting}>Cancel</Button>
              </Dialog.Close>
              <Button disabled={submitting || disabled} onClick={handleSubmit}>
                {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
                Create Department
              </Button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
