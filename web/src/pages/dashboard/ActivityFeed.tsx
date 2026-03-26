import { Activity } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { ActivityFeedItem } from './ActivityFeedItem'
import type { ActivityItem } from '@/api/types'

const MAX_VISIBLE = 10

interface ActivityFeedProps {
  activities: ActivityItem[]
}

export function ActivityFeed({ activities }: ActivityFeedProps) {
  const visible = activities.slice(0, MAX_VISIBLE)

  return (
    <SectionCard title="Activity" icon={Activity}>
      {visible.length === 0 ? (
        <EmptyState
          icon={Activity}
          title="No activity yet"
          description="Agent actions will appear here in real time"
        />
      ) : (
        <StaggerGroup className="divide-y divide-border">
          {visible.map((item) => (
            <StaggerItem key={item.id}>
              <ActivityFeedItem activity={item} />
            </StaggerItem>
          ))}
        </StaggerGroup>
      )}
    </SectionCard>
  )
}
