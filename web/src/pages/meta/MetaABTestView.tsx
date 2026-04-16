import { motion } from 'motion/react'

import { cn } from '@/lib/utils'
import { tweenDefault } from '@/lib/motion'
import { EmptyState } from '@/components/ui/empty-state'
import { MetricCard } from '@/components/ui/metric-card'
import { FlaskConical } from 'lucide-react'

import type { ABTestSummary } from '@/api/endpoints/meta'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import { formatCurrency } from '@/utils/format'

type ABTestVerdict = NonNullable<ABTestSummary['verdict']>

interface MetaABTestViewProps {
  tests: readonly ABTestSummary[]
}

const verdictLabels: Record<ABTestVerdict, string> = {
  treatment_wins: 'Treatment Wins',
  control_wins: 'Control Wins',
  inconclusive: 'Inconclusive',
  treatment_regressed: 'Treatment Regressed',
}

const verdictColors: Record<ABTestVerdict, string> = {
  treatment_wins: 'bg-success/15 text-success',
  control_wins: 'bg-warning/15 text-warning',
  inconclusive: 'bg-muted text-muted-foreground',
  treatment_regressed: 'bg-danger/15 text-danger',
}

export function MetaABTestView({ tests }: MetaABTestViewProps) {
  if (tests.length === 0) {
    return (
      <EmptyState
        icon={FlaskConical}
        title="No Active A/B Tests"
        description="A/B tests will appear here when a proposal uses the ab_test rollout strategy."
      />
    )
  }

  return (
    <div className="space-y-section-gap">
      {tests.map((test) => (
        <ABTestCard key={test.proposal_id} test={test} />
      ))}
    </div>
  )
}

function ABTestCard({ test }: { test: ABTestSummary }) {
  const progress =
    test.observation_hours_total > 0
      ? Math.min(
          (test.observation_hours_elapsed / test.observation_hours_total) * 100,
          100,
        )
      : 0

  return (
    <div className="rounded-lg border border-border bg-card p-card">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-foreground">
            {test.proposal_title}
          </h3>
          <p className="text-xs text-muted-foreground">
            {test.observation_hours_elapsed.toFixed(1)}h /{' '}
            {test.observation_hours_total}h observation
          </p>
        </div>
        {test.verdict && (
          <span
            className={cn(
              'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
              verdictColors[test.verdict],
            )}
          >
            {verdictLabels[test.verdict]}
          </span>
        )}
      </div>

      <div
        className="mb-4 h-1.5 w-full rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={Math.round(progress)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Observation progress: ${test.observation_hours_elapsed.toFixed(1)}h of ${test.observation_hours_total}h`}
      >
        <motion.div
          className="h-full rounded-full bg-accent"
          animate={{ width: `${progress}%` }}
          transition={tweenDefault}
        />
      </div>

      <div className="grid grid-cols-2 gap-grid-gap">
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Control ({test.control_metrics.agent_count} {test.control_metrics.agent_count === 1 ? 'agent' : 'agents'})
          </p>
          <div className="space-y-2">
            <MetricCard
              label="Quality"
              value={test.control_metrics.avg_quality_score}
            />
            <MetricCard
              label="Success Rate"
              value={`${(test.control_metrics.avg_success_rate * 100).toFixed(1)}%`}
            />
            <MetricCard
              label="Spend"
              value={formatCurrency(test.control_metrics.total_spend, DEFAULT_CURRENCY)}
            />
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Treatment ({test.treatment_metrics.agent_count} {test.treatment_metrics.agent_count === 1 ? 'agent' : 'agents'})
          </p>
          <div className="space-y-2">
            <MetricCard
              label="Quality"
              value={test.treatment_metrics.avg_quality_score}
            />
            <MetricCard
              label="Success Rate"
              value={`${(test.treatment_metrics.avg_success_rate * 100).toFixed(1)}%`}
            />
            <MetricCard
              label="Spend"
              value={formatCurrency(test.treatment_metrics.total_spend, DEFAULT_CURRENCY)}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
