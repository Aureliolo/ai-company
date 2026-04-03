import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'

const TRIGGER_OPTIONS = [
  { value: '', label: 'Select trigger...' },
  { value: 'sprint_start', label: 'Sprint Start (one-shot)' },
  { value: 'sprint_end', label: 'Sprint End (one-shot)' },
  { value: 'sprint_midpoint', label: 'Sprint Midpoint (one-shot)' },
  { value: 'every_n_completions', label: 'Every N Completions' },
  { value: 'sprint_percentage', label: 'Sprint Percentage' },
] as const

export interface TaskDrivenConfigProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  disabled?: boolean
}

export function TaskDrivenConfig({ config, onChange, disabled }: TaskDrivenConfigProps) {
  const trigger = (config.trigger as string) ?? ''
  const everyN = (config.every_n_completions as number) ?? 5
  const pct = (config.sprint_percentage as number) ?? 50

  return (
    <div className="space-y-3">
      <SelectField
        label="Trigger"
        options={TRIGGER_OPTIONS}
        value={trigger}
        onChange={(v) => onChange({ ...config, trigger: v })}
        disabled={disabled}
        hint="When to fire this ceremony"
      />

      {trigger === 'every_n_completions' && (
        <InputField
          label="Every N Completions"
          type="number"
          value={String(everyN)}
          onChange={(e) => { const val = Number(e.target.value); if (Number.isFinite(val)) onChange({ ...config, every_n_completions: val }) }}
          disabled={disabled}
          hint="Fire after every N task completions (min: 1)"
        />
      )}

      {trigger === 'sprint_percentage' && (
        <InputField
          label="Sprint Percentage"
          type="number"
          value={String(pct)}
          onChange={(e) => { const val = Number(e.target.value); if (Number.isFinite(val)) onChange({ ...config, sprint_percentage: val }) }}
          disabled={disabled}
          hint="Fire when this percentage of tasks complete (1-100)"
        />
      )}
    </div>
  )
}
