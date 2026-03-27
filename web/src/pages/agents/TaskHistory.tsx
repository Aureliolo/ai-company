import { ListTodo } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { TaskHistoryBar } from './TaskHistoryBar'
import type { Task } from '@/api/types'

interface TaskHistoryProps {
  tasks: readonly Task[]
  className?: string
}

export function TaskHistory({ tasks, className }: TaskHistoryProps) {
  // Sort by created_at descending (most recent first)
  const sorted = [...tasks]
    .filter((t) => t.created_at)
    .sort((a, b) => new Date(b.created_at!).getTime() - new Date(a.created_at!).getTime())

  // Compute max duration for relative bar widths
  const maxDurationMs = sorted.reduce((max, task) => {
    if (!task.created_at) return max
    const end = task.updated_at ?? task.created_at
    const duration = new Date(end).getTime() - new Date(task.created_at).getTime()
    return Math.max(max, duration)
  }, 1)

  return (
    <SectionCard title="Task History" icon={ListTodo} className={className}>
      {sorted.length === 0 ? (
        <EmptyState
          icon={ListTodo}
          title="No tasks yet"
          description="Task history will appear here as tasks are assigned."
        />
      ) : (
        <StaggerGroup className="space-y-1">
          {sorted.slice(0, 20).map((task) => (
            <StaggerItem key={task.id}>
              <TaskHistoryBar task={task} maxDurationMs={maxDurationMs} />
            </StaggerItem>
          ))}
        </StaggerGroup>
      )}
    </SectionCard>
  )
}
