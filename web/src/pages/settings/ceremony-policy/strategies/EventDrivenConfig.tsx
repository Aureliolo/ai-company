import { InputField } from '@/components/ui/input-field'

export interface EventDrivenConfigProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  disabled?: boolean
}

export function EventDrivenConfig({ config, onChange, disabled }: EventDrivenConfigProps) {
  const debounceDefault = (config.debounce_default as number) ?? 5
  const transitionEvent = (config.transition_event as string) ?? ''

  return (
    <div className="space-y-3">
      <InputField
        label="Default Debounce"
        type="number"
        value={String(debounceDefault)}
        onChange={(e) => {
          const val = Number(e.target.value)
          if (!Number.isFinite(val)) return
          onChange({ ...config, debounce_default: Math.min(10000, Math.max(1, Math.round(val))) })
        }}
        disabled={disabled}
        hint="Events required before firing (1-10000)"
      />

      <InputField
        label="Transition Event"
        value={transitionEvent}
        onChange={(e) => onChange({ ...config, transition_event: e.target.value })}
        disabled={disabled}
        hint="Event name that triggers sprint auto-transition (e.g. sprint_backlog_empty)"
      />
    </div>
  )
}
