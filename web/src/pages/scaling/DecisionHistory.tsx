import { Clock } from 'lucide-react'

import { EmptyState } from '@/components/ui/empty-state'
import { SectionCard } from '@/components/ui/section-card'
import { StatusBadge } from '@/components/ui/status-badge'
import type { ScalingDecisionResponse } from '@/api/endpoints/scaling'
import type { AgentRuntimeStatus } from '@/lib/utils'

interface DecisionHistoryProps {
  decisions: readonly ScalingDecisionResponse[]
}

const ACTION_STATUS_MAP: Record<string, AgentRuntimeStatus> = {
  hire: 'active',
  prune: 'error',
  hold: 'idle',
  no_op: 'offline',
}

export function DecisionHistory({ decisions }: DecisionHistoryProps) {
  return (
    <SectionCard title="Recent Decisions" icon={Clock}>
      {decisions.length === 0 ? (
        <EmptyState
          title="No recent decisions"
          description="Trigger an evaluation to generate scaling decisions"
        />
      ) : (
        <div className="flex flex-col gap-2">
          {decisions.map((decision) => (
            <div
              key={decision.id}
              className="flex items-center justify-between rounded-md border border-border p-card"
            >
              <div className="flex items-center gap-3">
                <StatusBadge
                  status={ACTION_STATUS_MAP[decision.action_type] ?? 'idle'}
                />
                <div className="flex flex-col">
                  <span className="font-medium text-foreground">
                    {decision.action_type.toUpperCase()}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {decision.rationale}
                  </span>
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <span className="text-sm text-muted-foreground">
                  {decision.source_strategy}
                </span>
                <span className="text-xs text-muted-foreground">
                  Confidence: {Math.round(decision.confidence * 100)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  )
}
