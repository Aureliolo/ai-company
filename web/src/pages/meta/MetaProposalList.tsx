import { Brain } from 'lucide-react'

import type { ProposalSummary } from '@/api/endpoints/meta'
import { EmptyState } from '@/components/ui/empty-state'
import { StatusBadge } from '@/components/ui/status-badge'
import type { AgentRuntimeStatus } from '@/lib/utils'

interface MetaProposalListProps {
  proposals: readonly ProposalSummary[]
}

const STATUS_MAP: Record<string, AgentRuntimeStatus> = {
  pending: 'idle',
  approved: 'active',
  rejected: 'error',
  applying: 'active',
  applied: 'active',
  rolled_back: 'offline',
  regressed: 'error',
}

export function MetaProposalList({ proposals }: MetaProposalListProps) {
  if (proposals.length === 0) {
    return (
      <EmptyState
        icon={Brain}
        title="No Proposals"
        description="Improvement proposals will appear here when the meta-loop detects actionable patterns."
      />
    )
  }

  return (
    <div className="space-y-2">
      {proposals.map((p) => (
        <div
          key={p.id}
          className="flex items-center justify-between rounded-md border border-border p-card"
        >
          <div className="flex items-center gap-3">
            <StatusBadge status={STATUS_MAP[p.status] ?? 'idle'} />
            <div>
              <p className="text-sm font-medium text-foreground">
                {p.title}
              </p>
              <p className="text-xs text-muted-foreground">
                {p.action_type} -- {p.risk_level}
              </p>
            </div>
          </div>
          <span className="text-xs capitalize text-muted-foreground">
            {p.status}
          </span>
        </div>
      ))}
    </div>
  )
}
