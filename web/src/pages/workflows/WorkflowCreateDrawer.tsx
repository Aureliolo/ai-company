import { useState } from 'react'
import { Drawer } from '@/components/ui/drawer'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import { Button } from '@/components/ui/button'
import { useWorkflowsStore } from '@/stores/workflows'
import { useToastStore } from '@/stores/toast'
import { WORKFLOW_TYPES } from '@/utils/constants'
import { getErrorMessage } from '@/utils/errors'
import { formatLabel } from '@/utils/format'

interface WorkflowCreateDrawerProps {
  open: boolean
  onClose: () => void
}

interface FormState {
  name: string
  description: string
  workflowType: string
}

const INITIAL_FORM: FormState = {
  name: '',
  description: '',
  workflowType: 'sequential_pipeline',
}

const WORKFLOW_TYPE_OPTIONS = WORKFLOW_TYPES.map((t) => ({
  value: t,
  label: formatLabel(t),
}))

export function WorkflowCreateDrawer({ open, onClose }: WorkflowCreateDrawerProps) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM)
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
    setSubmitError(null)
  }

  async function handleSubmit() {
    const next: Partial<Record<keyof FormState, string>> = {}
    if (!form.name.trim()) next.name = 'Name is required'
    setErrors(next)
    if (Object.keys(next).length > 0) return

    setSubmitting(true)
    try {
      await useWorkflowsStore.getState().createWorkflow({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        workflow_type: form.workflowType,
        nodes: [],
        edges: [],
      })
      useToastStore.getState().add({ variant: 'success', title: 'Workflow created' })
      setForm(INITIAL_FORM)
      setErrors({})
      setSubmitError(null)
      onClose()
    } catch (err) {
      setSubmitError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  function handleClose() {
    setForm(INITIAL_FORM)
    setErrors({})
    setSubmitError(null)
    onClose()
  }

  return (
    <Drawer open={open} onClose={handleClose} title="Create Workflow">
      <div className="flex flex-col gap-section-gap">
        <InputField
          label="Name"
          value={form.name}
          onChange={(e) => updateField('name', e.target.value)}
          error={errors.name}
          placeholder="Workflow name"
        />

        <InputField
          label="Description"
          value={form.description}
          onChange={(e) => updateField('description', e.target.value)}
          multiline
          placeholder="Optional description"
        />

        <SelectField
          label="Workflow Type"
          value={form.workflowType}
          onChange={(val) => updateField('workflowType', val)}
          options={WORKFLOW_TYPE_OPTIONS}
        />

        {submitError && (
          <div role="alert" aria-live="assertive" className="rounded-md border border-danger/30 bg-danger/5 p-card text-sm text-danger">
            {submitError}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={handleClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Creating...' : 'Create Workflow'}
          </Button>
        </div>
      </div>
    </Drawer>
  )
}
