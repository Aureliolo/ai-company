import { Link } from 'react-router'
import { Avatar } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import { formatRelativeTime } from '@/utils/format'
import type { ActivityItem } from '@/api/types'

interface ActivityFeedItemProps {
  activity: ActivityItem
  className?: string
}

export function ActivityFeedItem({ activity, className }: ActivityFeedItemProps) {
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-md px-3 py-2',
        'transition-colors duration-150',
        className,
      )}
    >
      <Avatar name={activity.agent_name} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-1.5">
          <span className="truncate text-sm font-semibold text-foreground">
            {activity.agent_name}
          </span>
          <span className="shrink-0 text-xs text-text-secondary">
            {activity.description}
          </span>
        </div>
        {activity.task_id && (
          <Link
            to={`/tasks/${activity.task_id}`}
            className="text-xs text-accent hover:underline"
          >
            {activity.task_id}
          </Link>
        )}
      </div>
      <span
        className="shrink-0 font-mono text-[10px] text-text-muted"
        data-testid="activity-timestamp"
      >
        {formatRelativeTime(activity.timestamp)}
      </span>
    </div>
  )
}
