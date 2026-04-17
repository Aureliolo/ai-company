import { MetricCard } from '@/components/ui/metric-card'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { cn } from '@/lib/utils'
import { formatTokenCount } from '@/utils/format'
import { countByStatus, totalTokensUsed } from '@/utils/meetings'
import type { MeetingResponse } from '@/api/types'

interface MeetingMetricCardsProps {
  meetings: readonly MeetingResponse[]
  className?: string
}

export function MeetingMetricCards({ meetings, className }: MeetingMetricCardsProps) {
  const total = meetings.length
  const inProgress = countByStatus(meetings, 'in_progress')
  const completed = countByStatus(meetings, 'completed')
  const tokens = totalTokensUsed(meetings)

  return (
    <StaggerGroup className={cn('grid grid-cols-2 gap-grid-gap lg:grid-cols-4', className)}>
      <StaggerItem>
        <MetricCard label="TOTAL MEETINGS" value={total} />
      </StaggerItem>
      <StaggerItem>
        <MetricCard label="IN PROGRESS" value={inProgress} />
      </StaggerItem>
      <StaggerItem>
        <MetricCard label="COMPLETED" value={completed} />
      </StaggerItem>
      <StaggerItem>
        <MetricCard label="TOTAL TOKENS" value={formatTokenCount(tokens)} />
      </StaggerItem>
    </StaggerGroup>
  )
}
