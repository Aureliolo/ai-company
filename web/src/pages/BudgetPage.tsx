import { useMemo, useState } from 'react'
import { AlertTriangle, WifiOff } from 'lucide-react'
import { MetricCard } from '@/components/ui/metric-card'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useBudgetData } from '@/hooks/useBudgetData'
import {
  computeAgentSpending,
  computeBudgetMetricCards,
  computeCategoryBreakdown,
  computeCostBreakdown,
  filterCfoEvents,
  getThresholdZone,
  type BreakdownDimension,
} from '@/utils/budget'
import { BudgetSkeleton } from './budget/BudgetSkeleton'
import { BudgetGauge } from './budget/BudgetGauge'
import { SpendBurnChart } from './budget/SpendBurnChart'
import { CostBreakdownChart } from './budget/CostBreakdownChart'
import { CategoryBreakdown } from './budget/CategoryBreakdown'
import { AgentSpendingTable } from './budget/AgentSpendingTable'
import { CfoActivityFeed } from './budget/CfoActivityFeed'
import { PeriodSelector } from './budget/PeriodSelector'
import { ThresholdAlerts } from './budget/ThresholdAlerts'

export default function BudgetPage() {
  const {
    overview,
    budgetConfig,
    forecast,
    costRecords,
    trends,
    activities,
    agentNameMap,
    agentDeptMap,
    aggregationPeriod,
    setAggregationPeriod,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useBudgetData()

  const [breakdownDimension, setBreakdownDimension] = useState<BreakdownDimension>('agent')

  const currency = overview?.currency ?? budgetConfig?.currency

  const thresholdZone = useMemo(
    () =>
      overview && budgetConfig
        ? getThresholdZone(overview.budget_used_percent, budgetConfig.alerts)
        : 'normal' as const,
    [overview, budgetConfig],
  )

  const metricCards = useMemo(
    () => (overview ? computeBudgetMetricCards(overview, budgetConfig, forecast) : []),
    [overview, budgetConfig, forecast],
  )

  const agentSpendingRows = useMemo(
    () => computeAgentSpending(costRecords, budgetConfig?.total_monthly ?? 0, agentNameMap),
    [costRecords, budgetConfig, agentNameMap],
  )

  const costBreakdown = useMemo(
    () => computeCostBreakdown(costRecords, breakdownDimension, agentNameMap, agentDeptMap),
    [costRecords, breakdownDimension, agentNameMap, agentDeptMap],
  )

  const categoryRatio = useMemo(
    () => computeCategoryBreakdown(costRecords),
    [costRecords],
  )

  const cfoEvents = useMemo(
    () => filterCfoEvents(activities),
    [activities],
  )

  if (loading && !overview) {
    return <BudgetSkeleton />
  }

  return (
    <div className="space-y-section-gap">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Budget</h1>
        <PeriodSelector value={aggregationPeriod} onChange={setAggregationPeriod} />
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {!wsConnected && !loading && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-card text-sm text-warning">
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      <ThresholdAlerts zone={thresholdZone} budgetConfig={budgetConfig} overview={overview} />

      <StaggerGroup className="grid grid-cols-4 gap-grid-gap max-[1023px]:grid-cols-2">
        {metricCards.map((card) => (
          <StaggerItem key={card.label}>
            <MetricCard {...card} />
          </StaggerItem>
        ))}
      </StaggerGroup>

      <div className="grid grid-cols-3 gap-grid-gap max-[1023px]:grid-cols-1">
        <ErrorBoundary level="section">
          <BudgetGauge
            usedPercent={overview?.budget_used_percent ?? 0}
            budgetRemaining={overview?.budget_remaining ?? 0}
            daysUntilExhausted={forecast?.days_until_exhausted ?? null}
            currency={currency}
          />
        </ErrorBoundary>
        <ErrorBoundary level="section">
          <div className="col-span-2 max-[1023px]:col-span-1">
            <SpendBurnChart
              trendData={trends?.data_points ?? []}
              forecast={forecast}
              budgetTotal={budgetConfig?.total_monthly ?? 0}
              budgetRemaining={overview?.budget_remaining}
              alerts={budgetConfig?.alerts}
              currency={currency}
            />
          </div>
        </ErrorBoundary>
      </div>

      <div className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1">
        <ErrorBoundary level="section">
          <CostBreakdownChart
            breakdown={costBreakdown}
            dimension={breakdownDimension}
            onDimensionChange={setBreakdownDimension}
            deptDisabled={agentDeptMap.size === 0}
            currency={currency}
          />
        </ErrorBoundary>
        <ErrorBoundary level="section">
          <CategoryBreakdown ratio={categoryRatio} currency={currency} />
        </ErrorBoundary>
      </div>

      <ErrorBoundary level="section">
        <AgentSpendingTable rows={agentSpendingRows} currency={currency} />
      </ErrorBoundary>

      <ErrorBoundary level="section">
        <CfoActivityFeed events={cfoEvents} />
      </ErrorBoundary>
    </div>
  )
}
