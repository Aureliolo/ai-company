import { MetricCard } from '@/components/ui/metric-card'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
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
    <StaggerGroup className={`grid grid-cols-2 gap-grid-gap lg:grid-cols-4${className ? ` ${className}` : ''}`}>
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
        <MetricCard label="TOTAL TOKENS" value={tokens.toLocaleString()} />
      </StaggerItem>
    </StaggerGroup>
  )
}
