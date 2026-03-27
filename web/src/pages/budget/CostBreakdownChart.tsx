import { useMemo } from 'react'
import { PieChart as PieChartIcon } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { cn } from '@/lib/utils'
import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { formatCurrency } from '@/utils/format'
import type { BreakdownDimension, BreakdownSlice } from '@/utils/budget'

export interface CostBreakdownChartProps {
  breakdown: readonly BreakdownSlice[]
  dimension: BreakdownDimension
  onDimensionChange: (dim: BreakdownDimension) => void
  deptDisabled?: boolean
  currency?: string
}

const DIMENSION_OPTIONS: { value: BreakdownDimension; label: string }[] = [
  { value: 'agent', label: 'Agent' },
  { value: 'department', label: 'Dept' },
  { value: 'provider', label: 'Provider' },
]

const MAX_LEGEND_SLICES = 6

function DonutTooltipContent({ active, payload, currency }: {
  active?: boolean
  payload?: Array<{ payload: BreakdownSlice }>
  currency?: string
}) {
  if (!active || !payload?.length) return null
  const slice = payload[0]!.payload
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-sans font-medium text-foreground">{slice.label}</p>
      <p className="font-mono text-foreground">{formatCurrency(slice.cost, currency)}</p>
      <p className="text-muted-foreground">{slice.percent.toFixed(1)}%</p>
    </div>
  )
}

export function CostBreakdownChart({
  breakdown,
  dimension,
  onDimensionChange,
  deptDisabled = false,
  currency,
}: CostBreakdownChartProps) {
  const legendSlices = useMemo(() => {
    if (breakdown.length <= MAX_LEGEND_SLICES) return breakdown
    const overflow = breakdown.slice(MAX_LEGEND_SLICES)
    return [
      ...breakdown.slice(0, MAX_LEGEND_SLICES),
      {
        key: '__other',
        label: 'Other',
        cost: overflow.reduce((sum, s) => sum + s.cost, 0),
        percent: overflow.reduce((sum, s) => sum + s.percent, 0),
        color: 'var(--so-text-muted)',
      },
    ]
  }, [breakdown])

  const chartData = useMemo(() => [...breakdown], [breakdown])

  return (
    <SectionCard
      title="Cost Breakdown"
      icon={PieChartIcon}
      action={
        <div
          role="radiogroup"
          aria-label="Breakdown dimension"
          className="flex rounded-lg border border-border"
        >
          {DIMENSION_OPTIONS.map((opt) => {
            const isActive = dimension === opt.value
            const isDisabled = opt.value === 'department' && deptDisabled
            return (
              <button
                key={opt.value}
                type="button"
                role="radio"
                aria-checked={isActive}
                disabled={isDisabled}
                onClick={() => { if (!isDisabled) onDimensionChange(opt.value) }}
                className={cn(
                  'px-3 py-1 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1',
                  isActive && 'bg-accent/10 text-accent font-medium',
                  !isActive && !isDisabled && 'text-text-muted hover:text-foreground',
                  isDisabled && 'opacity-50 cursor-not-allowed',
                )}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      }
    >
      {breakdown.length === 0 ? (
        <EmptyState
          icon={PieChartIcon}
          title="No cost data"
          description="Cost breakdown will appear when agents incur costs"
        />
      ) : (
        <div className="flex flex-col items-center gap-4">
          <div className="h-[200px] w-full" data-testid="cost-breakdown-chart">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey="cost"
                  nameKey="label"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={1}
                >
                  {breakdown.map((slice) => (
                    <Cell key={slice.key} fill={slice.color} />
                  ))}
                </Pie>
                <Tooltip content={<DonutTooltipContent currency={currency} />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-3" data-testid="cost-breakdown-legend">
            {legendSlices.map((slice) => (
              <div key={slice.key} className="flex items-center gap-1.5 text-xs">
                <span
                  className="size-2 shrink-0 rounded-full"
                  style={{ backgroundColor: slice.color }}
                  aria-hidden="true"
                />
                <span className="text-muted-foreground">{slice.label}</span>
                <span className="font-mono text-foreground">
                  {formatCurrency(slice.cost, currency)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  )
}
