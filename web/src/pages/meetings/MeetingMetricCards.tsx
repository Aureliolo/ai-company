import { MetricCard } from '@/components/ui/metric-card'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { countByStatus, totalTokensUsed } from '@/utils/meetings'
import type { MeetingResponse } from '@/api/types'

interface MeetingMetricCardsProps {
  meetings: readonly MeetingResponse[]
}

export function MeetingMetricCards({ meetings }: MeetingMetricCardsProps) {
  const total = meetings.length
  const inProgress = countByStatus(meetings, 'in_progress')
  const completed = countByStatus(meetings, 'completed')
  const tokens = totalTokensUsed(meetings)

  return (
    <StaggerGroup className="grid grid-cols-4 gap-grid-gap max-[1023px]:grid-cols-2">
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
