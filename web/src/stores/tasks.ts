import { create } from 'zustand'
import * as tasksApi from '@/api/endpoints/tasks'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import { createLogger } from '@/lib/logger'
import { useToastStore } from '@/stores/toast'
import type { Priority, TaskStatus, TaskType } from '@/api/types/enums'

const TASK_STATUS_VALUES: ReadonlySet<string> = new Set<TaskStatus>([
  'created', 'assigned', 'in_progress', 'in_review', 'completed',
  'blocked', 'failed', 'interrupted', 'suspended', 'cancelled',
  'rejected', 'auth_required',
])

const TASK_PRIORITY_VALUES: ReadonlySet<string> = new Set<Priority>([
  'critical', 'high', 'medium', 'low',
])

const TASK_TYPE_VALUES: ReadonlySet<string> = new Set<TaskType>([
  'development', 'design', 'research', 'review', 'meeting', 'admin',
])
import type {
  CancelTaskRequest,
  CreateTaskRequest,
  Task,
  TaskFilters,
  TransitionTaskRequest,
  UpdateTaskRequest,
} from '@/api/types/tasks'
import type { WsEvent } from '@/api/types/websocket'

const log = createLogger('tasks')

interface TasksState {
  // Data
  tasks: Task[]
  selectedTask: Task | null
  total: number

  // Loading states
  loading: boolean
  loadingDetail: boolean
  error: string | null

  // Actions. Mutations follow the canonical store error contract: on
  // failure they log + emit an error toast + return a sentinel
  // (`null` for entity-returning ops, `false` for delete). Callers MUST
  // NOT wrap these in try/catch; check the sentinel and branch on it.
  fetchTasks: (filters?: TaskFilters) => Promise<void>
  fetchTask: (taskId: string) => Promise<void>
  createTask: (data: CreateTaskRequest) => Promise<Task | null>
  updateTask: (taskId: string, data: UpdateTaskRequest) => Promise<Task | null>
  transitionTask: (taskId: string, data: TransitionTaskRequest) => Promise<Task | null>
  cancelTask: (taskId: string, data: CancelTaskRequest) => Promise<Task | null>
  deleteTask: (taskId: string) => Promise<boolean>

  // Real-time
  handleWsEvent: (event: WsEvent) => void

  // Optimistic helpers
  pendingTransitions: Set<string>
  optimisticTransition: (taskId: string, targetStatus: TaskStatus) => () => void
  upsertTask: (task: Task) => void
  removeTask: (taskId: string) => void
}

const pendingTransitions = new Set<string>()

/**
 * Type predicate verifying that a WS payload object carries every
 * field on the {@link Task} interface so consumers can use it without
 * a cast. Validates structural shape AND that enum-typed fields
 * (``status``, ``priority``, ``type``) carry values from their declared
 * unions so a malformed payload can't smuggle an illegal status into
 * the store.
 */
function isTaskShape(c: Record<string, unknown>): c is Record<string, unknown> & Task {
  return (
    typeof c.id === 'string' &&
    typeof c.status === 'string' &&
    TASK_STATUS_VALUES.has(c.status) &&
    typeof c.title === 'string' &&
    typeof c.priority === 'string' &&
    TASK_PRIORITY_VALUES.has(c.priority) &&
    typeof c.type === 'string' &&
    TASK_TYPE_VALUES.has(c.type) &&
    Array.isArray(c.dependencies) &&
    Array.isArray(c.acceptance_criteria)
  )
}

export const useTasksStore = create<TasksState>()((set, get) => ({
  tasks: [],
  selectedTask: null,
  total: 0,
  loading: false,
  loadingDetail: false,
  error: null,
  pendingTransitions,

  fetchTasks: async (filters) => {
    set({ loading: true, error: null })
    try {
      const result = await tasksApi.listTasks(filters)
      set({ tasks: result.data, total: result.total, loading: false })
    } catch (err) {
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  fetchTask: async (taskId) => {
    set({ loadingDetail: true })
    try {
      const task = await tasksApi.getTask(taskId)
      set({ selectedTask: task, loadingDetail: false })
    } catch (err) {
      set({ loadingDetail: false, error: getErrorMessage(err) })
    }
  },

  createTask: async (data) => {
    try {
      const task = await tasksApi.createTask(data)
      set((s) => ({ tasks: [task, ...s.tasks], total: s.total + 1 }))
      useToastStore.getState().add({
        variant: 'success',
        title: `Task ${task.title} created`,
      })
      return task
    } catch (err) {
      log.error('Create task failed:', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to create task',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  updateTask: async (taskId, data) => {
    try {
      const task = await tasksApi.updateTask(taskId, data)
      get().upsertTask(task)
      useToastStore.getState().add({
        variant: 'success',
        title: `Task ${task.title} updated`,
      })
      return task
    } catch (err) {
      log.error('Update task failed:', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to update task',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  transitionTask: async (taskId, data) => {
    try {
      const task = await tasksApi.transitionTask(taskId, data)
      get().upsertTask(task)
      useToastStore.getState().add({
        variant: 'success',
        title: `Task ${task.title} -> ${task.status}`,
      })
      return task
    } catch (err) {
      log.error('Transition task failed:', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to transition task',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  cancelTask: async (taskId, data) => {
    try {
      const task = await tasksApi.cancelTask(taskId, data)
      get().upsertTask(task)
      useToastStore.getState().add({
        variant: 'success',
        title: `Task ${task.title} cancelled`,
      })
      return task
    } catch (err) {
      log.error('Cancel task failed:', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to cancel task',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  deleteTask: async (taskId) => {
    try {
      await tasksApi.deleteTask(taskId)
      get().removeTask(taskId)
      useToastStore.getState().add({
        variant: 'success',
        title: 'Task deleted',
      })
      return true
    } catch (err) {
      log.error('Delete task failed:', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to delete task',
        description: getErrorMessage(err),
      })
      return false
    }
  },

  handleWsEvent: (event) => {
    const { payload } = event
    if (payload.task && typeof payload.task === 'object' && !Array.isArray(payload.task)) {
      const candidate = payload.task as Record<string, unknown>
      if (isTaskShape(candidate)) {
        if (pendingTransitions.has(candidate.id)) return
        get().upsertTask(candidate)
      } else {
        log.error('Received malformed task WS payload, skipping upsert', {
          id: sanitizeForLog(candidate.id),
          hasTitle: typeof candidate.title === 'string',
          hasStatus: typeof candidate.status === 'string',
        })
      }
    }
  },

  optimisticTransition: (taskId, targetStatus) => {
    const prev = get().tasks
    const taskIdx = prev.findIndex((t) => t.id === taskId)
    if (taskIdx === -1) return () => {}
    pendingTransitions.add(taskId)
    const oldTask = prev[taskIdx]!
    const updated = { ...oldTask, status: targetStatus }
    const newTasks = [...prev]
    newTasks[taskIdx] = updated
    set({ tasks: newTasks })
    return () => {
      pendingTransitions.delete(taskId)
      set({ tasks: prev })
    }
  },

  upsertTask: (task) => {
    pendingTransitions.delete(task.id)
    set((s) => {
      const idx = s.tasks.findIndex((t) => t.id === task.id)
      const newTasks = idx === -1 ? [task, ...s.tasks] : [...s.tasks]
      if (idx !== -1) newTasks[idx] = task
      const selectedTask = s.selectedTask?.id === task.id ? task : s.selectedTask
      return {
        tasks: newTasks,
        selectedTask,
        ...(idx === -1 ? { total: s.total + 1 } : {}),
      }
    })
  },

  removeTask: (taskId) => {
    set((s) => ({
      tasks: s.tasks.filter((t) => t.id !== taskId),
      total: Math.max(0, s.total - 1),
    }))
  },
}))
