/**
 * Training progress display for the onboarding checklist.
 *
 * Shows the LEARNED_FROM_SENIORS step status during onboarding,
 * with extraction and curation progress indicators.
 *
 * Visual testing checkpoints:
 * - Progress displays "Pending" when training not started
 * - Progress displays extraction/curation counts when in progress
 * - Progress displays "Complete" with result summary when done
 */

import { StatusBadge } from '@/components/ui/status-badge'
import { StatPill } from '@/components/ui/stat-pill'
import { cn } from '@/lib/utils'
import type { TrainingResultResponse } from '@/api/endpoints/training'

// -- Types -----------------------------------------------------------

interface TrainingProgressProps {
  status: 'pending' | 'in_progress' | 'complete' | 'skipped'
  result?: TrainingResultResponse | null
  className?: string
}

// -- Component -------------------------------------------------------

export function TrainingProgress({
  status,
  result,
  className,
}: TrainingProgressProps) {
  const statusMap = {
    pending: { badge: 'idle' as const, label: 'Pending' },
    in_progress: { badge: 'active' as const, label: 'In Progress' },
    complete: { badge: 'active' as const, label: 'Complete' },
    skipped: { badge: 'idle' as const, label: 'Skipped' },
  }

  const { badge, label } = statusMap[status]

  return (
    <div className={cn('flex items-center gap-grid-gap', className)}>
      <StatusBadge status={badge} label={label} />

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
