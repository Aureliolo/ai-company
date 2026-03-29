import { SegmentedControl, type SegmentedControlOption } from '@/components/ui/segmented-control'
import { AGGREGATION_PERIOD_VALUES, type AggregationPeriod } from '@/utils/budget'

export interface PeriodSelectorProps {
  value: AggregationPeriod
  onChange: (period: AggregationPeriod) => void
}

const PERIODS: readonly SegmentedControlOption<AggregationPeriod>[] = AGGREGATION_PERIOD_VALUES.map((v) => ({
  value: v,
  label: v.charAt(0).toUpperCase() + v.slice(1),
}))

export function PeriodSelector({ value, onChange }: PeriodSelectorProps) {
  return (
    <SegmentedControl
      label="Aggregation period"
      options={PERIODS}
      value={value}
      onChange={onChange}
    />
  )
}
