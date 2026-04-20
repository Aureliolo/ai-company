import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router'
import { ROUTES } from '@/router/routes'
import { useTasksStore } from '@/stores/tasks'
import { useToastStore } from '@/stores/toast'
import type { TaskStatus } from '@/api/types/enums'
import type { Task } from '@/api/types/tasks'
import { getTaskStatusLabel } from '@/utils/tasks'

export interface TaskActionHandlers {
  transitioning: TaskStatus | null
  transitionTo: (targetStatus: TaskStatus) => Promise<void>
  deleteTask: () => Promise<void>
  cancelTask: (reason: string) => Promise<boolean>
}

export function useTaskActionHandlers(task: Task | null | undefined): TaskActionHandlers {
  const navigate = useNavigate()
  const [transitioning, setTransitioning] = useState<TaskStatus | null>(null)

  const transitionTo = useCallback(
    async (targetStatus: TaskStatus) => {
      if (!task) return
      setTransitioning(targetStatus)
      try {
        await useTasksStore.getState().transitionTask(task.id, {
          target_status: targetStatus,
          expected_version: task.version,
        })
        useToastStore.getState().add({
          variant: 'success',
          title: `Task moved to ${getTaskStatusLabel(targetStatus)}`,
        })
      } catch {
        useToastStore.getState().add({ variant: 'error', title: 'Transition failed' })
      } finally {
        setTransitioning(null)
      }
    },
    [task],
  )

  const deleteTask = useCallback(async () => {
    if (!task) return
    try {
      await useTasksStore.getState().deleteTask(task.id)
      navigate(ROUTES.TASKS)
    } catch {
      useToastStore.getState().add({ variant: 'error', title: 'Failed to delete task' })
    }
  }, [task, navigate])

  const cancelTask = useCallback(
    async (reason: string) => {
      if (!task) return false
      const trimmed = reason.trim()
      if (!trimmed) {
        useToastStore.getState().add({
          variant: 'error',
          title: 'Please provide a cancellation reason',
        })
        return false
      }
      try {
        await useTasksStore.getState().cancelTask(task.id, { reason: trimmed })
        return true
      } catch {
        useToastStore.getState().add({ variant: 'error', title: 'Failed to cancel task' })
        return false
      }
    },
    [task],
  )

  return { transitioning, transitionTo, deleteTask, cancelTask }
}
