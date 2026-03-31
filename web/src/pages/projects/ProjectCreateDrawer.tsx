import { useState } from 'react'
import { Drawer } from '@/components/ui/drawer'
import { InputField } from '@/components/ui/input-field'
import { TagInput } from '@/components/ui/tag-input'
import { Button } from '@/components/ui/button'
import { useProjectsStore } from '@/stores/projects'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'

interface ProjectCreateDrawerProps {
  open: boolean
  onClose: () => void
}

interface FormState {
  name: string
  description: string
  team: string[]
  lead: string
  deadline: string
  budget: string
}

const INITIAL_FORM: FormState = {
  name: '',
  description: '',
  team: [],
  lead: '',
  deadline: '',
  budget: '',
}

export function ProjectCreateDrawer({ open, onClose }: ProjectCreateDrawerProps) {
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
    if (form.budget) {
      const parsed = Number(form.budget)
      if (!Number.isFinite(parsed) || parsed < 0) {
        next.budget = 'Budget must be a non-negative finite number'
      }
    }
    setErrors(next)
    if (Object.keys(next).length > 0) return

    setSubmitting(true)
    try {
      await useProjectsStore.getState().createProject({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        team: form.team.length > 0 ? form.team : undefined,
        lead: form.lead.trim() || undefined,
        deadline: form.deadline || undefined,
        budget: form.budget ? Number(form.budget) : undefined,
      })
      useToastStore.getState().add({ variant: 'success', title: 'Project created' })
      setForm(INITIAL_FORM)
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
    <Drawer open={open} onClose={handleClose} title="Create Project">
      <div className="flex flex-col gap-4">
        <InputField
          label="Name"
          value={form.name}
          onChange={(e) => updateField('name', e.target.value)}
          error={errors.name}
          placeholder="Project name"
        />

        <InputField
          label="Description"
          value={form.description}
          onChange={(e) => updateField('description', e.target.value)}
          multiline
          placeholder="Optional description"
        />

        <div role="group" aria-label="Team Members">
          <span className="mb-1.5 block text-sm font-medium text-foreground">
            Team Members
          </span>
          <TagInput
            value={form.team}
            onChange={(team) => updateField('team', team)}
            placeholder="Add agent ID and press Enter"
          />
        </div>

        <InputField
          label="Lead"
          value={form.lead}
          onChange={(e) => updateField('lead', e.target.value)}
          placeholder="Agent ID (optional)"
        />

        <InputField
          label="Deadline"
          type="date"
          value={form.deadline}
          onChange={(e) => updateField('deadline', e.target.value)}
        />

        <InputField
          label="Budget"
          type="number"
          value={form.budget}
          onChange={(e) => updateField('budget', e.target.value)}
          error={errors.budget}
          placeholder="0.00"
          hint="Budget in EUR"
        />

        {submitError && (
          <div className="rounded-md border border-danger/30 bg-danger/5 p-card text-sm text-danger">
            {submitError}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={handleClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Creating...' : 'Create Project'}
          </Button>
        </div>
      </div>
    </Drawer>
  )
}
