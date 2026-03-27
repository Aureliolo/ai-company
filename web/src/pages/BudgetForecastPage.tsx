import { useMemo } from 'react'
import { Link } from 'react-router'
import { AlertTriangle, ArrowLeft, Calendar, WifiOff } from 'lucide-react'
import { MetricCard } from '@/components/ui/metric-card'
import { SectionCard } from '@/components/ui/section-card'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { EmptyState } from '@/components/ui/empty-state'
import { SkeletonCard, SkeletonMetric, SkeletonTable } from '@/components/ui/skeleton'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useBudgetData } from '@/hooks/useBudgetData'
import { ROUTES } from '@/router/routes'
import { formatCurrency } from '@/utils/format'
import { computeExhaustionDate, type BudgetMetricCardData } from '@/utils/budget'
import { SpendBurnChart } from './budget/SpendBurnChart'
import type { ForecastPoint } from '@/api/types'

function ProjectionRow({ point, cumulative, currency, totalMonthly }: {
  point: ForecastPoint
  cumulative: number
  currency?: string
  totalMonthly: number
}) {
  const budgetPct = totalMonthly > 0 ? (cumulative / totalMonthly) * 100 : 0
  return (
    <div className="flex items-center gap-4 px-4 py-2">
      <span className="flex-1 font-mono text-xs text-foreground">{point.day}</span>
      <span className="w-28 text-right font-mono text-xs text-text-secondary">
        {formatCurrency(point.projected_spend_usd, currency)}
      </span>
      <span className="w-28 text-right font-mono text-xs text-text-secondary">
        {formatCurrency(cumulative, currency)}
      </span>
      <span className="w-24 text-right font-mono text-xs text-text-muted">
        {budgetPct.toFixed(1)}%
      </span>
    </div>
  )
}

export default function BudgetForecastPage() {
  const {
    overview,
    budgetConfig,
    forecast,
    trends,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useBudgetData()

  const currency = overview?.currency ?? budgetConfig?.currency

  const cumulativeValues = useMemo(() => {
    if (!forecast) return []
    let running = 0
    return forecast.daily_projections.map((p) => {
      running += p.projected_spend_usd
      return running
    })
  }, [forecast])

  const metricCards = useMemo((): BudgetMetricCardData[] => {
    if (!forecast) return []
    return [
      {
        label: 'PROJECTED TOTAL',
        value: formatCurrency(forecast.projected_total_usd, currency),
      },
      {
        label: 'DAYS UNTIL EXHAUSTED',
        value: forecast.days_until_exhausted != null
          ? String(forecast.days_until_exhausted)
          : 'N/A',
        subText: computeExhaustionDate(forecast.days_until_exhausted) ?? undefined,
      },
      {
        label: 'CONFIDENCE',
        value: Number.isFinite(forecast.confidence) ? `${Math.round(forecast.confidence * 100)}%` : '--',
      },
      {
        label: 'AVG DAILY SPEND',
        value: formatCurrency(forecast.avg_daily_spend_usd, currency),
      },
    ]
  }, [forecast, currency])

  if (loading && !overview) {
    return (
      <div className="space-y-6" role="status" aria-live="polite" aria-label="Loading forecast">
        <div className="grid grid-cols-4 gap-grid-gap max-[1023px]:grid-cols-2">
          <SkeletonMetric />
          <SkeletonMetric />
          <SkeletonMetric />
          <SkeletonMetric />
        </div>
        <SkeletonCard header lines={3} />
        <SkeletonTable rows={7} columns={4} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          to={ROUTES.BUDGET}
          className="text-text-muted transition-colors hover:text-foreground"
          aria-label="Back to Budget"
        >
          <ArrowLeft className="size-4" />
        </Link>
        <h1 className="text-lg font-semibold text-foreground">Budget Forecast</h1>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {!wsConnected && !loading && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-2 text-sm text-warning">
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      <StaggerGroup className="grid grid-cols-4 gap-grid-gap max-[1023px]:grid-cols-2">
        {metricCards.map((card) => (
          <StaggerItem key={card.label}>
            <MetricCard {...card} />
          </StaggerItem>
        ))}
      </StaggerGroup>

      <ErrorBoundary level="section">
        <SpendBurnChart
          trendData={trends?.data_points ?? []}
          forecast={forecast}
          budgetTotal={budgetConfig?.total_monthly ?? 0}
          budgetRemaining={overview?.budget_remaining_usd}
          alerts={budgetConfig?.alerts}
          currency={currency}
        />
      </ErrorBoundary>

      <SectionCard title="Daily Projections" icon={Calendar}>
        {forecast && forecast.daily_projections.length > 0 ? (
          <div className="rounded-lg border border-border">
            <div className="flex items-center gap-4 border-b border-border bg-surface px-4 py-2">
              <span className="flex-1 text-[11px] font-semibold uppercase tracking-wider text-text-muted">Day</span>
              <span className="w-28 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">Projected Spend</span>
              <span className="w-28 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">Cumulative</span>
              <span className="w-24 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">% of Budget</span>
            </div>
            <div className="divide-y divide-border">
              {forecast.daily_projections.map((point, idx) => (
                <ProjectionRow
                  key={point.day}
                  point={point}
                  cumulative={cumulativeValues[idx] ?? 0}
                  currency={currency}
                  totalMonthly={budgetConfig?.total_monthly ?? 0}
                />
              ))}
            </div>
          </div>
        ) : (
          <EmptyState
            icon={Calendar}
            title="No forecast data"
            description="Forecast projections will appear once enough spending data is available"
          />
        )}
      </SectionCard>
    </div>
  )
}
