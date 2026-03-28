import { useCallback, useEffect, useMemo, useState } from 'react'
import { Dialog } from 'radix-ui'
import { Loader2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import { getErrorMessage } from '@/utils/errors'
import type { AgentConfig, CreateAgentOrgRequest, Department, SeniorityLevel } from '@/api/types'
import { SENIORITY_LEVEL_VALUES } from '@/api/types'

export interface AgentCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  departments: readonly Department[]
  onCreate: (data: CreateAgentOrgRequest) => Promise<AgentConfig>
}

interface FormState {
  name: string
  role: string
  department: string
  level: SeniorityLevel
}

const INITIAL_FORM: FormState = {
  name: '',
  role: '',
  department: '',
  level: 'mid',
}

const LEVEL_OPTIONS = SENIORITY_LEVEL_VALUES.map((l) => ({ value: l, label: l }))

export function AgentCreateDialog({ open, onOpenChange, departments, onCreate }: AgentCreateDialogProps) {
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
    if (!form.name.trim()) next.name = 'Name is required'
    if (!form.role.trim()) next.role = 'Role is required'
    if (!form.department) next.department = 'Department is required'
    setErrors(next)
    if (Object.keys(next).length > 0) return

    setSubmitting(true)
    setSubmitError(null)
    try {
      await onCreate({
        name: form.name.trim(),
        role: form.role.trim(),
        department: form.department as CreateAgentOrgRequest['department'],
        level: form.level,
      })
      setForm(INITIAL_FORM)
      onOpenChange(false)
    } catch (err) {
      setSubmitError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }, [form, onCreate, onOpenChange])

  const deptOptions = useMemo(
    () => departments.map((d) => ({ value: d.name, label: d.display_name ?? d.name })),
    [departments],
  )

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
              New Agent
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
              placeholder="Agent name"
            />

            <InputField
              label="Role"
              value={form.role}
              onChange={(e) => updateField('role', e.target.value)}
              error={errors.role}
              required
              placeholder="e.g. Backend Developer"
            />

            <SelectField
              label="Department"
              options={deptOptions}
              value={form.department}
              onChange={(value) => updateField('department', value)}
              error={errors.department}
              required
              placeholder="Select department..."
            />

            <SelectField
              label="Level"
              options={LEVEL_OPTIONS}
              value={form.level}
              onChange={(value) => updateField('level', value as SeniorityLevel)}
            />

            {submitError && (
              <p className="text-xs text-danger">{submitError}</p>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Dialog.Close asChild>
                <Button variant="outline" disabled={submitting}>Cancel</Button>
              </Dialog.Close>
              <Button disabled={submitting} onClick={handleSubmit}>
                {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
                Create Agent
              </Button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
