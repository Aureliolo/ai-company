import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { DollarSign } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'
import { StatPill } from '@/components/ui/stat-pill'
import { EmptyState } from '@/components/ui/empty-state'
import { formatCurrency, formatCurrencyCompact } from '@/utils/format'
import type { ForecastResponse, TrendDataPoint } from '@/api/types'

interface BudgetBurnChartProps {
  trendData: readonly TrendDataPoint[]
  forecast: ForecastResponse | null
  budgetTotal: number
  budgetRemaining?: number
  currency?: string
}

interface ChartDataPoint {
  label: string
  actual?: number
  projected?: number
}

function buildChartData(
  trendData: readonly TrendDataPoint[],
  forecast: ForecastResponse | null,
): ChartDataPoint[] {
  let points: ChartDataPoint[] = trendData.map((p) => ({
    label: formatDayLabel(p.timestamp),
    actual: p.value,
  }))

  if (forecast && forecast.daily_projections.length > 0) {
    // Bridge: last actual point also gets projected value for continuity
    if (points.length > 0) {
      const last = points[points.length - 1]!
      points = [...points.slice(0, -1), { ...last, projected: last.actual }]
    }
    const forecastPoints: ChartDataPoint[] = forecast.daily_projections.map((fp) => ({
      label: formatDayLabel(fp.day),
      projected: fp.projected_spend_usd,
    }))
    points = [...points, ...forecastPoints]
  }

  return points
}

function parseChartDate(dateStr: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr)
  if (!match) return new Date(dateStr)
  const [, year, month, day] = match
  return new Date(Number(year), Number(month) - 1, Number(day))
}

function formatDayLabel(dateStr: string): string {
  const date = parseChartDate(dateStr)
  if (Number.isNaN(date.getTime())) return dateStr
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function getTodayLabel(): string {
  return new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function ChartTooltipContent({ active, payload, label }: {
  active?: boolean
  payload?: Array<{ value: number; dataKey: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-sans text-text-secondary">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} className="font-mono text-foreground">
          {entry.dataKey === 'projected' ? 'Forecast: ' : 'Spend: '}
          {formatCurrency(entry.value)}
        </p>
      ))}
    </div>
  )
}

export function BudgetBurnChart({ trendData, forecast, budgetTotal, budgetRemaining, currency }: BudgetBurnChartProps) {
  const chartData = buildChartData(trendData, forecast)
  const hasData = trendData.length > 0
  const todayLabel = getTodayLabel()

  return (
    <SectionCard
      title="Budget Burn"
      icon={DollarSign}
      action={
        <div className="flex gap-2">
          {budgetRemaining !== undefined && (
            <StatPill label="Remaining" value={formatCurrency(budgetRemaining, currency)} />
          )}
          {forecast && (
            <>
              <StatPill label="Avg/day" value={formatCurrency(forecast.avg_daily_spend_usd, forecast.currency)} />
              {forecast.days_until_exhausted !== null && (
                <StatPill label="Days left" value={forecast.days_until_exhausted} />
              )}
            </>
          )}
        </div>
      }
    >
      {!hasData ? (
        <EmptyState
          icon={DollarSign}
          title="No spend data available"
          description="Cost records will appear as agents consume tokens"
        />
      ) : (
        <div className="h-48 w-full" data-testid="budget-burn-chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 20, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--so-border)"
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: 'var(--so-text-muted)' }}
                axisLine={{ stroke: 'var(--so-border)' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 10, fill: 'var(--so-text-muted)' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => formatCurrencyCompact(v, currency)}
                width={48}
              />
              <Tooltip content={<ChartTooltipContent />} />

              {budgetTotal > 0 && (
                <ReferenceLine
                  y={budgetTotal}
                  stroke="var(--so-danger)"
                  strokeDasharray="4 4"
                  strokeWidth={1}
                  label={{
                    value: 'Budget',
                    position: 'right',
                    fontSize: 10,
                    fill: 'var(--so-danger)',
                  }}
                />
              )}

              <ReferenceLine
                x={todayLabel}
                stroke="var(--so-text-muted)"
                strokeDasharray="3 3"
                strokeWidth={1}
                label={{
                  value: 'Today',
                  position: 'top',
                  fontSize: 10,
                  fill: 'var(--so-text-muted)',
                }}
              />

              <defs>
                <linearGradient id="actualFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--so-accent)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--so-accent)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--so-warning)" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="var(--so-warning)" stopOpacity={0} />
                </linearGradient>
              </defs>

              <Area
                type="monotone"
                dataKey="actual"
                stroke="var(--so-accent)"
                fill="url(#actualFill)"
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
              />
              {forecast && (
                <Area
                  type="monotone"
                  dataKey="projected"
                  stroke="var(--so-warning)"
                  fill="url(#forecastFill)"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  dot={false}
                  connectNulls={false}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </SectionCard>
  )
}
