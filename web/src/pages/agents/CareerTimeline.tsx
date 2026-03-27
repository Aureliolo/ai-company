import { History } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { CareerTimelineEvent } from './CareerTimelineEvent'
import type { CareerEvent } from '@/api/types'

interface CareerTimelineProps {
  events: readonly CareerEvent[]
  className?: string
}

export function CareerTimeline({ events, className }: CareerTimelineProps) {
  return (
    <SectionCard title="Career Timeline" icon={History} className={className}>
      {events.length === 0 ? (
        <EmptyState
          icon={History}
          title="No career events"
          description="Career milestones will appear here as they occur."
        />
      ) : (
        <StaggerGroup>
          {events.map((event, i) => (
            <StaggerItem key={`${event.event_type}-${event.timestamp}-${i}`}>
              <CareerTimelineEvent
                event={event}
                isLast={i === events.length - 1}
              />
            </StaggerItem>
          ))}
        </StaggerGroup>
      )}
    </SectionCard>
  )
}
