import { Avatar } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import { formatLabel, formatTokenCount } from '@/utils/format'
import { getPhaseColor, getPhaseLabel, STATUS_BADGE_CLASSES } from '@/utils/meetings'
import type { MeetingContribution } from '@/api/types'

interface ContributionBubbleProps {
  contribution: MeetingContribution
  className?: string
}

export function ContributionBubble({ contribution, className }: ContributionBubbleProps) {
  const phaseColor = getPhaseColor(contribution.phase)
  const phaseBadgeClass = STATUS_BADGE_CLASSES[phaseColor]

  return (
    <div className={cn('flex gap-3', className)}>
      <Avatar name={contribution.agent_id} size="sm" />
      <div className="min-w-0 flex-1 space-y-1.5">
        {/* Header */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">
            {formatLabel(contribution.agent_id)}
          </span>
          <span
            className={cn(
              'shrink-0 rounded-full border px-1.5 py-0.5 text-micro font-medium',
              phaseBadgeClass,
            )}
          >
            {getPhaseLabel(contribution.phase)}
          </span>
          <span className="text-micro text-muted-foreground">
            Turn {contribution.turn_number}
          </span>
        </div>

        {/* Content */}
        <p className="whitespace-pre-wrap text-sm text-foreground leading-relaxed">
          {contribution.content}
        </p>

        {/* Token stats */}
        <div className="flex gap-3 font-mono text-micro text-muted-foreground">
          <span>{formatTokenCount(contribution.input_tokens)} in</span>
          <span>{formatTokenCount(contribution.output_tokens)} out</span>
        </div>
      </div>
    </div>
  )
}
