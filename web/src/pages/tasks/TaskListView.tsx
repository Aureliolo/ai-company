import { cn } from '@/lib/utils'
import { Avatar } from '@/components/ui/avatar'
import { TaskStatusIndicator } from '@/components/ui/task-status-indicator'
import { PriorityBadge } from '@/components/ui/task-status-indicator'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { EmptyState } from '@/components/ui/empty-state'
import { getTaskTypeLabel } from '@/utils/tasks'
import { formatRelativeTime, formatCurrency } from '@/utils/format'
import { Inbox } from 'lucide-react'
import type { Task } from '@/api/types'

export interface TaskListViewProps {
  tasks: Task[]
  onSelectTask: (taskId: string) => void
}

const COLUMNS = [
  { key: 'status', label: 'Status', width: 'w-20' },
  { key: 'title', label: 'Title', width: 'flex-1' },
  { key: 'assignee', label: 'Assignee', width: 'w-32' },
  { key: 'priority', label: 'Priority', width: 'w-24' },
  { key: 'type', label: 'Type', width: 'w-24' },
  { key: 'deadline', label: 'Deadline', width: 'w-24' },
  { key: 'cost', label: 'Cost', width: 'w-20' },
] as const

export function TaskListView({ tasks, onSelectTask }: TaskListViewProps) {
  if (tasks.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="No tasks found"
        description="Try adjusting your filters or create a new task"
      />
    )
  }

  return (
    <div className="rounded-lg border border-border">
      {/* Table header */}
      <div className="flex items-center gap-4 border-b border-border bg-surface px-4 py-2">
        {COLUMNS.map((col) => (
          <span
            key={col.key}
            className={cn('text-[11px] font-semibold uppercase tracking-wider text-text-muted', col.width)}
          >
            {col.label}
          </span>
        ))}
      </div>

      {/* Table body */}
      <StaggerGroup className="divide-y divide-border">
        {tasks.map((task) => (
          <StaggerItem key={task.id}>
            <div
              role="button"
              tabIndex={0}
              onClick={() => onSelectTask(task.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelectTask(task.id)
                }
              }}
              className="flex cursor-pointer items-center gap-4 px-4 py-3 transition-colors hover:bg-card-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent"
              aria-label={`Task: ${task.title}`}
            >
              <span className="w-20">
                <TaskStatusIndicator status={task.status} label />
              </span>
              <span className="flex-1 truncate text-[13px] font-medium text-foreground">
                {task.title}
              </span>
              <span className="w-32">
                {task.assigned_to ? (
                  <span className="flex items-center gap-1.5">
                    <Avatar name={task.assigned_to} size="sm" />
                    <span className="truncate text-xs text-text-secondary">{task.assigned_to}</span>
                  </span>
                ) : (
                  <span className="text-xs text-text-muted">Unassigned</span>
                )}
              </span>
              <span className="w-24">
                <PriorityBadge priority={task.priority} />
              </span>
              <span className="w-24 text-xs text-text-secondary">
                {getTaskTypeLabel(task.type)}
              </span>
              <span className="w-24 font-mono text-[10px] text-text-muted">
                {task.deadline ? formatRelativeTime(task.deadline) : '--'}
              </span>
              <span className="w-20 text-right font-mono text-[10px] text-text-muted">
                {task.cost_usd != null ? formatCurrency(task.cost_usd) : '--'}
              </span>
            </div>
          </StaggerItem>
        ))}
      </StaggerGroup>
    </div>
  )
}
