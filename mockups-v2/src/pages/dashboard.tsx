import { motion } from "framer-motion"
import { useTheme } from "@/themes/provider.tsx"
import { MetricCard } from "@/components/metric-card.tsx"
import { DeptHealthBar } from "@/components/dept-health-bar.tsx"
import { ActivityStream } from "@/components/activity-stream.tsx"
import { BudgetChart } from "@/components/budget-chart.tsx"
import { SectionCard } from "@/components/section-card.tsx"
import { metrics, departments, activityFeed, budgetHistory, budgetSummary } from "@/data/index.ts"

export function Dashboard() {
  const theme = useTheme()
  const { density, animation } = theme

  return (
    <div className={`${density.cardPadding} flex flex-col ${density.sectionGap}`}>
      {/* Page header */}
      <div>
        <h1 className="text-lg font-semibold text-text-primary tracking-tight">
          Overview
        </h1>
        <p className="text-text-muted font-mono text-xs mt-0.5">
          Mon, Mar 23 2026 -- 15:42 UTC
        </p>
      </div>

      {/* Row 1: Metric cards */}
      <motion.div
        className={`grid grid-cols-4 ${density.gridGap}`}
        initial="hidden"
        animate="visible"
        variants={{
          visible: {
            transition: { staggerChildren: animation.staggerChildren },
          },
        }}
      >
        <MetricCard
          label="Tasks Today"
          value="24"
          change={`+${metrics.tasks.change}%`}
          changePositive
          trend={metrics.tasks.trend}
          trendColor="var(--theme-accent)"
        />
        <MetricCard
          label="Active Agents"
          value={String(metrics.agents.active)}
          sub={`of ${metrics.agents.total}`}
          trend={metrics.agents.trend}
          trendColor="var(--theme-accent)"
        />
        <MetricCard
          label="Spend Today"
          value={`$${metrics.spend.value.toFixed(2)}`}
          sub={`${metrics.spend.percent}% of daily budget`}
          trend={metrics.spend.trend}
          trendColor="var(--theme-warning)"
          subColor="text-warning"
          progressValue={metrics.spend.percent}
          progressColor="var(--theme-warning)"
        />
        <MetricCard
          label="Approvals"
          value={String(metrics.approvals.value)}
          sub="awaiting review"
          trend={metrics.approvals.trend}
          trendColor="var(--theme-danger)"
          subColor="text-danger"
        />
      </motion.div>

      {/* Row 2: Org Health */}
      <SectionCard label="Org Health" sublabel="Department performance -- last 24h">
        <div className="flex flex-col gap-2.5">
          {departments.map((dept) => (
            <DeptHealthBar key={dept.name} dept={dept} />
          ))}
        </div>
      </SectionCard>

      {/* Row 3: Activity + Budget */}
      <div className="grid grid-cols-2 gap-4">
        <SectionCard label="Activity Stream" sublabel="Real-time agent actions">
          <ActivityStream events={activityFeed.slice(0, 12)} />
        </SectionCard>

        <SectionCard
          label="Budget Burn"
          sublabel={`Actual vs forecast -- $${budgetSummary.remaining.toFixed(0)} remaining`}
        >
          <BudgetChart data={budgetHistory} summary={budgetSummary} />
        </SectionCard>
      </div>
    </div>
  )
}
