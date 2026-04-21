import { MetricCard } from '@/components/ui/metric-card'
import { ErrorBanner } from '@/components/ui/error-banner'
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
  } = useDashboardData()

  if (loading && !overview) {
    return <DashboardSkeleton />
  }

  const metricCards = overview ? computeMetricCards(overview, budgetConfig) : []

  return (
    <div className="space-y-section-gap">
      <h1 className="text-lg font-semibold text-foreground">Overview</h1>

      {error && (
        <ErrorBanner severity="error" title="Could not load dashboard" description={error} />
      )}

      <StaggerGroup className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
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
          budgetRemaining={overview?.budget_remaining}
          currency={overview?.currency}
        />
      </ErrorBoundary>
    </div>
  )
}
