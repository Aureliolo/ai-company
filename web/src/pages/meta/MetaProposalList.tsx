import { EmptyState } from '@/components/ui/empty-state'
import { Brain } from 'lucide-react'

interface MetaProposalListProps {
  proposals: unknown[]
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

  // Placeholder: real implementation renders proposal cards with
  // approve/reject actions, rationale, rollback plan, etc.
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {proposals.length} proposal(s) pending review
      </p>
    </div>
  )
}
