import { motion } from 'motion/react'
import { Check, X as XIcon, Minus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { springDefault, tweenExitFast } from '@/lib/motion'
import { formatNumber } from '@/utils/format'

export interface BatchActionBarProps {
  selectedCount: number
  onApproveAll: () => void
  onRejectAll: () => void
  onClearSelection: () => void
  loading?: boolean
}

const BAR_VARIANTS = {
  initial: { y: '100%', opacity: 0 },
  animate: { y: 0, opacity: 1, transition: springDefault },
  exit: { y: '100%', opacity: 0, transition: tweenExitFast },
}

export function BatchActionBar({
  selectedCount,
  onApproveAll,
  onRejectAll,
  onClearSelection,
  loading,
}: BatchActionBarProps) {
  return (
    <motion.div
      className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-center px-4 pb-4"
      variants={BAR_VARIANTS}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <div className="flex items-center gap-3 rounded-lg border border-border bg-surface px-4 py-2.5 shadow-[var(--so-shadow-card-hover)]" role="toolbar" aria-label="Batch actions">
        <span className="text-sm font-medium text-foreground" aria-live="polite">
          {formatNumber(selectedCount)} selected
        </span>

        <div className="h-4 w-px bg-border" aria-hidden="true" />

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

        <div className="h-4 w-px bg-border" aria-hidden="true" />

        <Button
          size="sm"
          variant="ghost"
          className="gap-1 text-muted-foreground"
          onClick={onClearSelection}
          disabled={loading}
        >
          <Minus className="size-3.5" />
          Clear
        </Button>
      </div>
    </motion.div>
  )
}
