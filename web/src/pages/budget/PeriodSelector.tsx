import { cn } from '@/lib/utils'
import type { AggregationPeriod } from '@/utils/budget'

export interface PeriodSelectorProps {
  value: AggregationPeriod
  onChange: (period: AggregationPeriod) => void
}

const PERIODS: { value: AggregationPeriod; label: string }[] = [
  { value: 'hourly', label: 'Hourly' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
]

export function PeriodSelector({ value, onChange }: PeriodSelectorProps) {
  return (
    <div
      role="radiogroup"
      aria-label="Aggregation period"
      className="flex rounded-lg border border-border"
    >
      {PERIODS.map((period) => (
        <button
          key={period.value}
          role="radio"
          aria-checked={value === period.value}
          type="button"
          onClick={() => onChange(period.value)}
          className={cn(
            'px-3 py-1 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1',
            value === period.value
              ? 'bg-accent/10 text-accent font-medium'
              : 'text-text-muted hover:text-foreground',
          )}
        >
          {period.label}
        </button>
      ))}
    </div>
  )
}
