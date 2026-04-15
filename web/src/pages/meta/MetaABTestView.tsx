import { motion } from 'motion/react'

import { cn } from '@/lib/utils'
import { tweenDefault } from '@/lib/motion'
import { EmptyState } from '@/components/ui/empty-state'
import { MetricCard } from '@/components/ui/metric-card'
import { FlaskConical } from 'lucide-react'

/** Metrics for a single A/B test group (control or treatment). */
export interface ABTestGroupMetrics {
  group: 'control' | 'treatment'
  agentCount: number
  observationCount: number
  avgQualityScore: number
  avgSuccessRate: number
  totalSpendUsd: number
}

/** A/B test verdict from the comparator. */
export type ABTestVerdict =
  | 'treatment_wins'
  | 'control_wins'
  | 'inconclusive'
  | 'treatment_regressed'

/** Summary of an active A/B test. */
export interface ABTestSummary {
  proposalId: string
  proposalTitle: string
  controlMetrics: ABTestGroupMetrics
  treatmentMetrics: ABTestGroupMetrics
  verdict: ABTestVerdict | null
  observationHoursElapsed: number
  observationHoursTotal: number
}

interface MetaABTestViewProps {
  tests: ABTestSummary[]
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
        <ABTestCard key={test.proposalId} test={test} />
      ))}
    </div>
  )
}

function ABTestCard({ test }: { test: ABTestSummary }) {
  const progress =
    test.observationHoursTotal > 0
      ? Math.min(
          (test.observationHoursElapsed / test.observationHoursTotal) * 100,
          100,
        )
      : 0

  return (
    <div className="rounded-lg border border-border bg-card p-card">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-foreground">
            {test.proposalTitle}
          </h3>
          <p className="text-xs text-muted-foreground">
            {test.observationHoursElapsed.toFixed(1)}h /{' '}
            {test.observationHoursTotal}h observation
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
        aria-label={`Observation progress: ${test.observationHoursElapsed.toFixed(1)}h of ${test.observationHoursTotal}h`}
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
            Control ({test.controlMetrics.agentCount} agents)
          </p>
          <div className="space-y-2">
            <MetricCard
              label="Quality"
              value={test.controlMetrics.avgQualityScore}
            />
            <MetricCard
              label="Success Rate"
              value={`${(test.controlMetrics.avgSuccessRate * 100).toFixed(1)}%`}
            />
            <MetricCard
              label="Spend"
              value={`$${test.controlMetrics.totalSpendUsd.toFixed(2)}`}
            />
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Treatment ({test.treatmentMetrics.agentCount} agents)
          </p>
          <div className="space-y-2">
            <MetricCard
              label="Quality"
              value={test.treatmentMetrics.avgQualityScore}
            />
            <MetricCard
              label="Success Rate"
              value={`${(test.treatmentMetrics.avgSuccessRate * 100).toFixed(1)}%`}
            />
            <MetricCard
              label="Spend"
              value={`$${test.treatmentMetrics.totalSpendUsd.toFixed(2)}`}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
