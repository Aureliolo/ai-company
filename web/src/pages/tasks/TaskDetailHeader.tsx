import { InlineEdit } from '@/components/ui/inline-edit'
import { PriorityBadge, TaskStatusIndicator } from '@/components/ui/task-status-indicator'
import { useTasksStore } from '@/stores/tasks'
import { useToastStore } from '@/stores/toast'
import type { Task } from '@/api/types/tasks'
import { getErrorMessage } from '@/utils/errors'

interface TaskDetailHeaderProps {
  task: Task
}

export function TaskDetailHeader({ task }: TaskDetailHeaderProps) {
  return (
    <div className="flex items-start justify-between">
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <TaskStatusIndicator status={task.status} label />
          <PriorityBadge priority={task.priority} />
        </div>
        <InlineEdit
          value={task.title}
          onSave={async (value) => {
            try {
              await useTasksStore.getState().updateTask(task.id, {
                title: value,
                expected_version: task.version,
              })
            } catch (err) {
              useToastStore.getState().add({
                variant: 'error',
                title: 'Failed to save title',
                description: getErrorMessage(err),
              })
              throw err
            }
          }}
          validate={(v) => (v.trim().length === 0 ? 'Title is required' : null)}
          className="text-xl font-semibold"
        />
      </div>
    </div>
  )
}
