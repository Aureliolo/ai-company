import { useCallback, useState } from 'react'
import { Dialog } from '@base-ui/react/dialog'
import { Loader2, X } from 'lucide-react'
import { cn, FOCUS_RING } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { getErrorMessage } from '@/utils/errors'
import type { CreateTaskRequest, Priority, TaskType, Complexity } from '@/api/types'

export interface TaskCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (data: CreateTaskRequest) => Promise<void>
}

const TASK_TYPES: { value: TaskType; label: string }[] = [
  { value: 'development', label: 'Development' },
  { value: 'design', label: 'Design' },
  { value: 'research', label: 'Research' },
  { value: 'review', label: 'Review' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'admin', label: 'Admin' },
]

const PRIORITIES: { value: Priority; label: string }[] = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

const COMPLEXITIES: { value: Complexity; label: string }[] = [
  { value: 'simple', label: 'Simple' },
  { value: 'medium', label: 'Medium' },
  { value: 'complex', label: 'Complex' },
  { value: 'epic', label: 'Epic' },
]

interface FormState {
  title: string
  description: string
  type: TaskType
  priority: Priority
  project: string
  created_by: string
  assigned_to: string
  estimated_complexity: Complexity
  budget_limit: string
}

interface TaskTemplate {
  label: string
  description: string
  defaults: Partial<FormState>
}

const TASK_TEMPLATES: TaskTemplate[] = [
  {
    label: 'Development',
    description: 'Code implementation task',
    defaults: { type: 'development', estimated_complexity: 'medium', priority: 'medium' },
  },
  {
    label: 'Bug Fix',
    description: 'Fix a reported issue',
    defaults: { type: 'development', estimated_complexity: 'simple', priority: 'high' },
  },
  {
    label: 'Research',
    description: 'Investigate or evaluate an approach',
    defaults: { type: 'research', estimated_complexity: 'medium', priority: 'medium' },
  },
  {
    label: 'Code Review',
    description: 'Review submitted work',
    defaults: { type: 'review', estimated_complexity: 'simple', priority: 'medium' },
  },
]

const INITIAL_FORM: FormState = {
  title: '',
  description: '',
  type: 'development',
  priority: 'medium',
  project: '',
  created_by: '',
  assigned_to: '',
  estimated_complexity: 'medium',
  budget_limit: '',
}

export function TaskCreateDialog({ open, onOpenChange, onCreate }: TaskCreateDialogProps) {
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
    if (!form.title.trim()) next.title = 'Title is required'
    if (!form.description.trim()) next.description = 'Description is required'
    if (!form.project.trim()) next.project = 'Project is required'
    if (!form.created_by.trim()) next.created_by = 'Creator is required'
    if (form.budget_limit !== '') {
      const n = Number(form.budget_limit)
      if (!Number.isFinite(n) || n < 0) next.budget_limit = 'Budget must be a non-negative number'
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const handleSubmit = useCallback(async () => {
    if (!validate()) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const data: CreateTaskRequest = {
        title: form.title.trim(),
        description: form.description.trim(),
        type: form.type,
        priority: form.priority,
        project: form.project.trim(),
        created_by: form.created_by.trim(),
        assigned_to: form.assigned_to.trim() || undefined,
        estimated_complexity: form.estimated_complexity,
        budget_limit: form.budget_limit ? Number(form.budget_limit) : undefined,
      }
      await onCreate(data)
      setForm(INITIAL_FORM)
      onOpenChange(false)
    } catch (err) {
      setSubmitError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  // eslint-disable-next-line @eslint-react/exhaustive-deps -- validate reads form which is in deps
  }, [form, onCreate, onOpenChange])

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm transition-opacity duration-200 ease-out data-[closed]:opacity-0 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0" />
        <Dialog.Popup
          className={cn(
            'fixed top-1/2 left-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2',
            'rounded-xl border border-border-bright bg-surface p-6 shadow-lg',
            'transition-[opacity,transform,scale] duration-200 ease-out',
            'data-[closed]:opacity-0 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0',
            'data-[closed]:scale-95 data-[starting-style]:scale-95 data-[ending-style]:scale-95',
            'max-h-[85vh] overflow-y-auto',
          )}
        >
          <div className="flex items-center justify-between mb-4">
            <Dialog.Title className="text-base font-semibold text-foreground">
              New Task
            </Dialog.Title>
            <Dialog.Close
              render={
                <Button variant="ghost" size="icon" aria-label="Close">
                  <X className="size-4" />
                </Button>
              }
            />
          </div>

          <div className="space-y-4">
            {/* Template suggestions */}
            <div>
              <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Start from template
              </label>
              <div className="flex flex-wrap gap-1.5">
                {TASK_TEMPLATES.map((tpl) => (
                  <button
                    key={tpl.label}
                    type="button"
                    onClick={() => setForm((prev) => ({ ...prev, ...tpl.defaults }))}
                    className="rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:border-accent hover:text-foreground"
                    title={tpl.description}
                  >
                    {tpl.label}
                  </button>
                ))}
              </div>
            </div>

            <FormField label="Title" error={errors.title} required>
              <input
                type="text"
                value={form.title}
                onChange={(e) => updateField('title', e.target.value)}
                className={INPUT_CLASSES}
                placeholder="Task title"
                autoFocus
              />
            </FormField>

            <FormField label="Description" error={errors.description} required>
              <textarea
                value={form.description}
                onChange={(e) => updateField('description', e.target.value)}
                className={cn(TEXTAREA_CLASSES, 'min-h-[80px]')}
                placeholder="Describe the task..."
                rows={3}
              />
            </FormField>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Type">
                <select value={form.type} onChange={(e) => updateField('type', e.target.value as TaskType)} className={INPUT_CLASSES}>
                  {TASK_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </FormField>

              <FormField label="Priority">
                <select value={form.priority} onChange={(e) => updateField('priority', e.target.value as Priority)} className={INPUT_CLASSES}>
                  {PRIORITIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </FormField>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Project" error={errors.project} required>
                <input type="text" value={form.project} onChange={(e) => updateField('project', e.target.value)} className={INPUT_CLASSES} placeholder="Project name" />
              </FormField>

              <FormField label="Created By" error={errors.created_by} required>
                <input type="text" value={form.created_by} onChange={(e) => updateField('created_by', e.target.value)} className={INPUT_CLASSES} placeholder="Agent or user" />
              </FormField>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Assigned To">
                <input type="text" value={form.assigned_to} onChange={(e) => updateField('assigned_to', e.target.value)} className={INPUT_CLASSES} placeholder="Agent name (optional)" />
              </FormField>

              <FormField label="Complexity">
                <select value={form.estimated_complexity} onChange={(e) => updateField('estimated_complexity', e.target.value as Complexity)} className={INPUT_CLASSES}>
                  {COMPLEXITIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </FormField>
            </div>

            <FormField label="Budget Limit">
              <input type="number" value={form.budget_limit} onChange={(e) => updateField('budget_limit', e.target.value)} className={INPUT_CLASSES} placeholder="0.00" min="0" step="0.01" />
            </FormField>

            {submitError && (
              <p className="text-xs text-danger">{submitError}</p>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Dialog.Close
                render={
                  <Button variant="outline" disabled={submitting}>Cancel</Button>
                }
              />
              <Button disabled={submitting} onClick={handleSubmit}>
                {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
                Create Task
              </Button>
            </div>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

const INPUT_CLASSES = cn('w-full h-8 rounded-md border border-border bg-surface px-2 text-[13px] text-foreground outline-none', FOCUS_RING)
const TEXTAREA_CLASSES = cn('w-full rounded-md border border-border bg-surface px-2 py-1.5 text-[13px] text-foreground outline-none resize-y', FOCUS_RING)

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

export { INPUT_CLASSES, TEXTAREA_CLASSES }
