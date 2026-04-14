import { EmptyState } from '@/components/ui/empty-state'
import { Brain } from 'lucide-react'

/** Minimal proposal shape for display purposes. */
export interface ProposalSummary {
  id: string
  title: string
  altitude: string
  status: string
  confidence: number
}

interface MetaProposalListProps {
  proposals: ProposalSummary[]
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
    <div className="space-y-section-gap">
      <p className="text-sm text-muted-foreground">
        {proposals.length} proposal(s) pending review
      </p>
    </div>
  )
}
