import { useState } from 'react'
import { InputField } from '@/components/ui/input-field'
import { LazyCodeMirrorEditor } from '@/components/ui/lazy-code-mirror-editor'

export interface MilestoneDrivenConfigProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  disabled?: boolean
}

export function MilestoneDrivenConfig({ config, onChange, disabled }: MilestoneDrivenConfigProps) {
  const milestones = config.milestones ?? []
  const transitionMilestone = (config.transition_milestone as string) ?? ''
  const [jsonError, setJsonError] = useState<string | null>(null)

  return (
    <div className="space-y-3">
      <div>
        <p className="mb-1 text-sm font-medium text-foreground">Milestones</p>
        <p className="mb-2 text-xs text-text-secondary">
          JSON array of milestone definitions with name and ceremony fields
        </p>
        <LazyCodeMirrorEditor
          value={JSON.stringify(milestones, null, 2)}
          onChange={(val) => {
            try {
              onChange({ ...config, milestones: JSON.parse(val) })
              setJsonError(null)
            } catch {
              setJsonError('Invalid JSON')
            }
          }}
          language="json"
          readOnly={disabled}
          className="max-h-48"
        />
        {jsonError && (
          <p className="mt-1 text-xs text-danger">{jsonError}</p>
        )}
      </div>

      <InputField
        label="Transition Milestone"
        value={transitionMilestone}
        onChange={(e) => onChange({ ...config, transition_milestone: e.target.value })}
        disabled={disabled}
        hint="Milestone name that triggers sprint auto-transition"
      />
    </div>
  )
}
