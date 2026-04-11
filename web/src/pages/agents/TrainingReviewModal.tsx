/**
 * Training review gate modal.
 *
 * Displays training items pending human review and provides
 * approve/reject actions. Integrates with the approval store.
 *
 * Visual testing checkpoints:
 * - Modal opens with list of pending training items
 * - Approve button calls onApprove callback
 * - Reject button calls onReject callback
 * - Empty state when no items pending
 */

import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { StatPill } from '@/components/ui/stat-pill'
import { cn } from '@/lib/utils'
import { createLogger } from '@/lib/logger'

const log = createLogger('training-review-modal')

// -- Types -----------------------------------------------------------

interface TrainingReviewItem {
  content_type: string
  item_count: number
  source_agents: string[]
}

interface TrainingReviewModalProps {
  open: boolean
  planId: string
  approvalId: string
  items: TrainingReviewItem[]
  onApprove: () => void | Promise<void>
  onReject?: () => void
  onOpenChange: (open: boolean) => void
  loading?: boolean
}

// -- Content type labels ---------------------------------------------

const CONTENT_TYPE_LABELS: Record<string, string> = {
  procedural: 'Procedural Memories',
  semantic: 'Semantic Knowledge',
  tool_patterns: 'Tool Patterns',
}

// -- Component -------------------------------------------------------

export function TrainingReviewModal({
  open,
  planId,
  approvalId,
  items,
  onApprove,
  onReject,
  onOpenChange,
  loading = false,
}: TrainingReviewModalProps) {
  const totalItems = items.reduce((sum, item) => sum + item.item_count, 0)

  const handleApprove = () => {
    log.debug('Approving training plan', { planId, approvalId })
    return onApprove()
  }

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onReject?.()
        onOpenChange(nextOpen)
      }}
      onConfirm={handleApprove}
      title="Review Training Plan"
      confirmLabel="Approve"
      cancelLabel="Reject"
      loading={loading}
    >
      <div className="space-y-card">
        <p className="text-sm text-muted-foreground">
          Review {totalItems} training items before they are seeded
          into the new agent&apos;s memory.
        </p>

        <div className="flex flex-wrap gap-grid-gap">
          <StatPill label="Total Items" value={totalItems} />
          <StatPill label="Plan" value={planId.slice(0, 8)} />
        </div>

        {/* Per-content-type breakdown */}
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={item.content_type}
              className={cn(
                'flex items-center justify-between',
                'rounded-md bg-muted/50 p-card text-sm',
              )}
            >
              <span className="text-foreground">
                {CONTENT_TYPE_LABELS[item.content_type] ?? item.content_type}
              </span>
              <div className="flex gap-grid-gap">
                <span className="font-mono text-muted-foreground">
                  {item.item_count} items
                </span>
                <span className="text-muted-foreground">
                  from {item.source_agents.length} agent(s)
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </ConfirmDialog>
  )
}
