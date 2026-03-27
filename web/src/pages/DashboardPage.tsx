import { AlertTriangle, WifiOff } from 'lucide-react'
import { MetricCard } from '@/components/ui/metric-card'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useDashboardData } from '@/hooks/useDashboardData'
import { computeMetricCards } from '@/utils/dashboard'
import { DashboardSkeleton } from './dashboard/DashboardSkeleton'
import { OrgHealthSection } from './dashboard/OrgHealthSection'
import { ActivityFeed } from './dashboard/ActivityFeed'
import { BudgetBurnChart } from './dashboard/BudgetBurnChart'

export default function DashboardPage() {
  const {
    overview,
    forecast,
    departmentHealths,
    activities,
    budgetConfig,
    orgHealthPercent,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useDashboardData()

  if (loading && !overview) {
    return <DashboardSkeleton />
  }

  const metricCards = overview ? computeMetricCards(overview, budgetConfig) : []

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-foreground">Overview</h1>

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

      <div className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1">
        <ErrorBoundary level="section">
          <OrgHealthSection
            departments={departmentHealths}
            overallHealth={orgHealthPercent}
          />
        </ErrorBoundary>
        <ErrorBoundary level="section">
          <ActivityFeed activities={activities} />
        </ErrorBoundary>
      </div>

      <ErrorBoundary level="section">
        <BudgetBurnChart
          trendData={overview?.cost_7d_trend ?? []}
          forecast={forecast}
          budgetTotal={budgetConfig?.total_monthly ?? 0}
          budgetRemaining={overview?.budget_remaining_usd}
        />
      </ErrorBoundary>
    </div>
  )
}
