import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'

const FREQUENCY_OPTIONS = [
  { value: '', label: 'Select frequency...' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'bi_weekly', label: 'Bi-Weekly' },
  { value: 'per_sprint_day', label: 'Per Sprint Day' },
  { value: 'monthly', label: 'Monthly' },
] as const

export interface CalendarConfigProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  disabled?: boolean
}

export function CalendarConfig({ config, onChange, disabled }: CalendarConfigProps) {
  const frequency = (config.frequency as string) ?? ''
  const durationDays = (config.duration_days as number) ?? 14

  return (
    <div className="space-y-3">
      <SelectField
        label="Frequency"
        options={FREQUENCY_OPTIONS}
        value={frequency}
        onChange={(v) => onChange({ ...config, frequency: v })}
        disabled={disabled}
        hint="How often ceremonies fire"
      />

      <InputField
        label="Duration (days)"
        type="number"
        value={String(durationDays)}
        onChange={(e) => { const val = Number(e.target.value); if (Number.isFinite(val)) onChange({ ...config, duration_days: val }) }}
        disabled={disabled}
        hint="Sprint duration in calendar days (1-90)"
      />
    </div>
  )
}
