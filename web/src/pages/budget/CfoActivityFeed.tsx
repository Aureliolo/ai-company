import { ScrollText } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { ActivityFeedItem } from '@/pages/dashboard/ActivityFeedItem'
import type { ActivityItem } from '@/api/types/analytics'

const MAX_VISIBLE = 10

export interface CfoActivityFeedProps {
  events: readonly ActivityItem[]
}

export function CfoActivityFeed({ events }: CfoActivityFeedProps) {
  const visible = events.slice(0, MAX_VISIBLE)

  return (
    <SectionCard title="CFO Optimization Events" icon={ScrollText}>
      {visible.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="No budget events"
          description="Budget decisions and alerts will appear here"
        />
      ) : (
        <div role="log" aria-live="polite">
          <StaggerGroup className="divide-y divide-border">
            {visible.map((item) => (
              <StaggerItem key={item.id}>
                <ActivityFeedItem activity={item} />
              </StaggerItem>
            ))}
          </StaggerGroup>
        </div>
      )}
    </SectionCard>
  )
}
