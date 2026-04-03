import { InputField } from '@/components/ui/input-field'

export interface ThroughputAdaptiveConfigProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  disabled?: boolean
}

export function ThroughputAdaptiveConfig({ config, onChange, disabled }: ThroughputAdaptiveConfigProps) {
  const dropPct = (config.velocity_drop_threshold_pct as number) ?? 30
  const spikePct = (config.velocity_spike_threshold_pct as number) ?? 50
  const window = (config.measurement_window_tasks as number) ?? 10

  return (
    <div className="space-y-3">
      <InputField
        label="Velocity Drop Threshold (%)"
        type="number"
        value={String(dropPct)}
        onChange={(e) => onChange({ ...config, velocity_drop_threshold_pct: Number(e.target.value) })}
        disabled={disabled}
        hint="Trigger ceremony when velocity drops by this percentage (1-100)"
      />

      <InputField
        label="Velocity Spike Threshold (%)"
        type="number"
        value={String(spikePct)}
        onChange={(e) => onChange({ ...config, velocity_spike_threshold_pct: Number(e.target.value) })}
        disabled={disabled}
        hint="Trigger ceremony when velocity spikes by this percentage (1-100)"
      />

      <InputField
        label="Measurement Window (tasks)"
        type="number"
        value={String(window)}
        onChange={(e) => onChange({ ...config, measurement_window_tasks: Number(e.target.value) })}
        disabled={disabled}
        hint="Rolling window of task completions for rate calculation (2-100)"
      />
    </div>
  )
}
