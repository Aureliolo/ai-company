import { InputField } from '@/components/ui/input-field'

export interface BudgetDrivenConfigProps {
  config: Record<string, unknown>
  onChange: (config: Record<string, unknown>) => void
  disabled?: boolean
}

export function BudgetDrivenConfig({ config, onChange, disabled }: BudgetDrivenConfigProps) {
  const thresholds = (config.budget_thresholds as number[]) ?? [25, 50, 75, 100]
  const transitionPct = (config.transition_threshold as number) ?? 100

  return (
    <div className="space-y-3">
      <InputField
        label="Budget Thresholds (%)"
        value={thresholds.join(', ')}
        onChange={(e) => {
          const parsed = e.target.value
            .split(',')
            .map((s) => Number(s.trim()))
            .filter((n) => Number.isFinite(n) && n > 0 && n <= 100)
          if (Array.isArray(parsed)) onChange({ ...config, budget_thresholds: parsed })
        }}
        disabled={disabled}
        hint="Comma-separated budget percentages that trigger ceremonies (e.g. 25, 50, 75)"
      />

      <InputField
        label="Transition Threshold (%)"
        type="number"
        value={String(transitionPct)}
        onChange={(e) => { const val = Number(e.target.value); if (Number.isFinite(val)) onChange({ ...config, transition_threshold: val }) }}
        disabled={disabled}
        hint="Budget percentage that triggers sprint auto-transition (1-100)"
      />
    </div>
  )
}
