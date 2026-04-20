import { cn } from '@/lib/utils'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { MeetingTimelineNode } from './MeetingTimelineNode'
import type { MeetingResponse } from '@/api/types/meetings'

interface MeetingTimelineProps {
  meetings: readonly MeetingResponse[]
  className?: string
}

export function MeetingTimeline({ meetings, className }: MeetingTimelineProps) {
  if (meetings.length === 0) return null

  return (
    <div className={cn('relative', className)}>
      {/* Horizontal connector line */}
      <div
        className="pointer-events-none absolute left-4 right-4 top-1/2 h-px bg-border"
        aria-hidden="true"
      />
      <StaggerGroup
        className="flex gap-3 overflow-x-auto pb-2 snap-x snap-mandatory scrollbar-thin"
      >
        {meetings.map((meeting) => (
          <StaggerItem key={meeting.meeting_id}>
            <MeetingTimelineNode meeting={meeting} />
          </StaggerItem>
        ))}
      </StaggerGroup>
    </div>
  )
}
