import { useCallback, useState } from 'react'
import { Dialog } from 'radix-ui'
import { Loader2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
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

const INPUT_CLASSES = 'w-full h-8 rounded-md border border-border bg-surface px-2 text-[13px] text-foreground outline-none focus:ring-2 focus:ring-accent focus:ring-offset-1'

export function AgentCreateDialog({ open, onOpenChange, departments, onCreate }: AgentCreateDialogProps) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM)
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
    setSubmitError(null)
  }

  function validate(): boolean {
    const next: Partial<Record<keyof FormState, string>> = {}
    if (!form.name.trim()) next.name = 'Name is required'
    if (!form.role.trim()) next.role = 'Role is required'
    if (!form.department) next.department = 'Department is required'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const handleSubmit = useCallback(async () => {
    if (!validate()) return
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
  // eslint-disable-next-line @eslint-react/exhaustive-deps -- validate reads form
  }, [form, onCreate, onOpenChange])

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
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
            <FormField label="Name" error={errors.name} required>
              <input
                type="text"
                value={form.name}
                onChange={(e) => updateField('name', e.target.value)}
                className={INPUT_CLASSES}
                placeholder="Agent name"
                autoFocus
              />
            </FormField>

            <FormField label="Role" error={errors.role} required>
              <input
                type="text"
                value={form.role}
                onChange={(e) => updateField('role', e.target.value)}
                className={INPUT_CLASSES}
                placeholder="e.g. Backend Developer"
              />
            </FormField>

            <FormField label="Department" error={errors.department} required>
              <select
                value={form.department}
                onChange={(e) => updateField('department', e.target.value)}
                className={INPUT_CLASSES}
              >
                <option value="">Select department...</option>
                {departments.map((d) => (
                  <option key={d.name} value={d.name}>{d.display_name}</option>
                ))}
              </select>
            </FormField>

            <FormField label="Level">
              <select
                value={form.level}
                onChange={(e) => updateField('level', e.target.value as SeniorityLevel)}
                className={INPUT_CLASSES}
              >
                {SENIORITY_LEVEL_VALUES.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </FormField>

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

function FormField({ label, error, required, children }: { label: string; error?: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        {label}{required && <span className="text-danger"> *</span>}
      </label>
      {children}
      {error && <p className="mt-0.5 text-[10px] text-danger">{error}</p>}
    </div>
  )
}
