import { MetricCard } from '@/components/ui/metric-card'
import { ToggleField } from '@/components/ui/toggle-field'
import { SliderField } from '@/components/ui/slider-field'
import { formatCurrency } from '@/utils/format'
import type { CostEstimate } from '@/utils/cost-estimator'

export interface CostEstimatePanelProps {
  estimate: CostEstimate | null
  currency: string
  budgetCapEnabled: boolean
  budgetCap: number | null
  onBudgetCapEnabledChange: (enabled: boolean) => void
  onBudgetCapChange: (cap: number | null) => void
}

export function CostEstimatePanel({
  estimate,
  currency,
  budgetCapEnabled,
  budgetCap,
  onBudgetCapEnabledChange,
  onBudgetCapChange,
}: CostEstimatePanelProps) {
  if (!estimate) return null

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-4">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">Cost Estimate</h3>
        <p className="text-xs text-muted-foreground">
          Based on {estimate.assumptions.dailyTokensPerAgent.toLocaleString()} tokens/agent/day
        </p>
      </div>

      <MetricCard
        label="Estimated Monthly Cost"
        value={formatCurrency(estimate.monthlyTotal, currency)}
      />

      <div className="space-y-3 border-t border-border pt-3">
        <ToggleField
          label="Set a budget limit"
          description="Budget enforcement prevents agents from exceeding this limit."
          checked={budgetCapEnabled}
          onChange={onBudgetCapEnabledChange}
        />
        {budgetCapEnabled && (
          <SliderField
            label="Monthly Budget Cap"
            value={budgetCap ?? Math.ceil(estimate.monthlyTotal * 2)}
            min={Math.ceil(estimate.monthlyTotal)}
            max={Math.max(Math.ceil(estimate.monthlyTotal * 10), 1000)}
            step={10}
            formatValue={(v) => formatCurrency(v, currency)}
            onChange={(v) => onBudgetCapChange(v)}
          />
        )}
      </div>

      <p className="text-compact text-muted-foreground">
        * Actual costs depend on task volume and complexity. This is a rough projection for planning purposes.
        {estimate.usedFallback && (
          <> Estimate uses average tier pricing -- actual costs depend on your model configuration.</>
        )}
      </p>
    </div>
  )
}
