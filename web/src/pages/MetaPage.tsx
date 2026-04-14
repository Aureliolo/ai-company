import { Brain, RefreshCw, Settings2, Shield } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { MetricCard } from '@/components/ui/metric-card'
import { SectionCard } from '@/components/ui/section-card'

import { MetaProposalList, type ProposalSummary } from './meta/MetaProposalList'
import { MetaRuleStatus } from './meta/MetaRuleStatus'
import { MetaSignalOverview } from './meta/MetaSignalOverview'

export default function MetaPage() {
  // Placeholder: real implementation wires up useMetaData() hook.
  const loading = false
  const enabled = false
  const proposals: ProposalSummary[] = []

  if (!enabled) {
    return (
      <div className="mx-auto max-w-7xl p-card">
        <EmptyState
          icon={Brain}
          title="Self-Improvement Disabled"
          description="Enable the self-improvement meta-loop in your company configuration to see improvement proposals, org signals, and rollout status."
        />
      </div>
    )
  }

  return (
    <ErrorBoundary level="page">
      <div className="mx-auto max-w-7xl space-y-section-gap p-card">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">
              Company Self-Improvement
            </h1>
            <p className="text-sm text-muted-foreground">
              Meta-loop signals, proposals, and rollout status
            </p>
          </div>
          <Button variant="outline" size="sm" disabled={loading}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Trigger Cycle
          </Button>
        </header>

        <div className="grid grid-cols-1 gap-grid-gap md:grid-cols-3">
          <MetricCard label="Pending Proposals" value={proposals.length} />
          <MetricCard label="Active Rollouts" value={0} />
          <MetricCard label="Rules Firing" value={0} />
        </div>

        <div className="grid grid-cols-1 gap-grid-gap lg:grid-cols-2">
          <SectionCard title="Signal Overview" icon={Settings2}>
            <MetaSignalOverview />
          </SectionCard>

          <SectionCard title="Rule Status" icon={Shield}>
            <MetaRuleStatus />
          </SectionCard>
        </div>

        <SectionCard title="Improvement Proposals" icon={Brain}>
          <MetaProposalList proposals={proposals} />
        </SectionCard>
      </div>
    </ErrorBoundary>
  )
}
