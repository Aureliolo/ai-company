import { Check, X as XIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { BulkActionBar } from '@/components/ui/bulk-action-bar'
import { formatNumber } from '@/utils/format'

export interface BatchActionBarProps {
  selectedCount: number
  onApproveAll: () => void
  onRejectAll: () => void
  onClearSelection: () => void
  loading?: boolean
}

/**
 * Approvals-specific wrapper around the shared `BulkActionBar` primitive.
 *
 * Keeps the two well-known actions (Approve / Reject) and the count-aware
 * labels, but delegates layout, motion, the "N selected" left label, the
 * Clear button, and accessibility wiring to the shared bar so future
 * spacing / a11y / loading-state fixes stay in one place.
 */
export function BatchActionBar({
  selectedCount,
  onApproveAll,
  onRejectAll,
  onClearSelection,
  loading,
}: BatchActionBarProps) {
  return (
    <BulkActionBar
      selectedCount={selectedCount}
      onClear={onClearSelection}
      loading={loading}
      ariaLabel="Batch actions"
    >
      <Button
        size="sm"
        variant="outline"
        className="gap-1 border-success/30 text-success hover:bg-success/10"
        onClick={onApproveAll}
        disabled={loading}
      >
        <Check className="size-3.5" />
        Approve {formatNumber(selectedCount)}
      </Button>

      <Button
        size="sm"
        variant="outline"
        className="gap-1 border-danger/30 text-danger hover:bg-danger/10"
        onClick={onRejectAll}
        disabled={loading}
      >
        <XIcon className="size-3.5" />
        Reject {formatNumber(selectedCount)}
      </Button>
    </BulkActionBar>
  )
}
