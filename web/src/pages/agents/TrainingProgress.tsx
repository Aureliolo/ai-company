/**
 * Training progress display for the onboarding checklist.
 *
 * Shows the LEARNED_FROM_SENIORS step status during onboarding.
 * In the "complete" state it also shows a result summary with
 * item and source counts.
 *
 * Visual testing checkpoints:
 * - Displays "Pending" when training is not yet started
 * - Displays "In Progress" while the pipeline is running
 * - Displays "Complete" with the result summary when finished
 * - Displays "Skipped" when training was bypassed
 */

import { StatPill } from '@/components/ui/stat-pill'
import { cn } from '@/lib/utils'
import type { TrainingResultResponse } from '@/api/endpoints/training'

// -- Types -----------------------------------------------------------

type TrainingStatus = 'pending' | 'in_progress' | 'complete' | 'skipped'

interface TrainingProgressProps {
  status: TrainingStatus
  result?: TrainingResultResponse | null
  className?: string
}

// -- Status labels ---------------------------------------------------

const STATUS_LABELS: Record<TrainingStatus, string> = {
  pending: 'Pending',
  in_progress: 'In Progress',
  complete: 'Complete',
  skipped: 'Skipped',
}

// -- Component -------------------------------------------------------

export function TrainingProgress({
  status,
  result,
  className,
}: TrainingProgressProps) {
  return (
    <div className={cn('flex items-center gap-grid-gap', className)}>
      <span className="text-sm text-muted-foreground">
        {STATUS_LABELS[status]}
      </span>

      {status === 'complete' && result && (
        <div className="flex gap-grid-gap">
          <StatPill
            label="Items"
            value={result.items_stored.reduce(
              (sum, [, count]) => sum + count,
              0,
            )}
          />
          <StatPill
            label="Sources"
            value={result.source_agents_used.length}
          />
        </div>
      )}
    </div>
  )
}
