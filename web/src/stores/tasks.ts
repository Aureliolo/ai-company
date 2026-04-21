import { create } from 'zustand'
import * as tasksApi from '@/api/endpoints/tasks'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import { createLogger } from '@/lib/logger'
import { sanitizeWsString } from '@/stores/notifications'
import { useToastStore } from '@/stores/toast'
import {
  PRIORITY_VALUES,
  TASK_STATUS_VALUES as TASK_STATUS_VALUES_TUPLE,
  TASK_TYPE_VALUES as TASK_TYPE_VALUES_TUPLE,
} from '@/api/types/enums'
import type { TaskStatus } from '@/api/types/enums'

// Runtime-check sets derived from the canonical enum tuples in
// `@/api/types/enums`. Building them here (rather than re-declaring the
// literal list) keeps the validator in lockstep with the type union
// -- drift between the runtime check and the declared enum is caught
// at compile time.
const TASK_STATUS_SET: ReadonlySet<string> = new Set<string>(TASK_STATUS_VALUES_TUPLE)
const TASK_PRIORITY_SET: ReadonlySet<string> = new Set<string>(PRIORITY_VALUES)
const TASK_TYPE_SET: ReadonlySet<string> = new Set<string>(TASK_TYPE_VALUES_TUPLE)
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
 * Minimum structural check for a ``Task``-shaped WS payload. Validates
 * the required identifier + enum-typed fields (``status``, ``priority``,
 * ``type`` -- each checked against the canonical enum tuple so illegal
 * values cannot be smuggled in) and the two required array fields
 * (``dependencies``, ``acceptance_criteria``). Additional ``Task``
 * fields (``created_at``, ``updated_at``, ``assigned_to``, ...) are
 * intentionally not checked here -- the server is the source of truth
 * for those and the guard stays focused on the fields the store reads.
 */
/**
 * Return a sanitized copy of a ``Task`` with every untrusted string
 * field routed through ``sanitizeWsString`` so control chars and
 * bidi overrides never reach the rendered UI. ``dependencies`` is a
 * string array; ``acceptance_criteria`` is an array of objects whose
 * ``description`` is the only freeform string field (``met`` is a
 * boolean validated by the shape guard already).
 */
function sanitizeTask(c: Task): Task {
  return {
    ...c,
    title: sanitizeWsString(c.title, 256) ?? '',
    description: sanitizeWsString(c.description, 4096) ?? '',
    dependencies: c.dependencies
      .map((dep) => sanitizeWsString(dep, 128) ?? '')
      .filter((dep) => dep.length > 0),
    acceptance_criteria: c.acceptance_criteria.map((ac) => ({
      ...ac,
      description: sanitizeWsString(ac.description, 512) ?? '',
    })),
  }
}

/** Each ``dependencies`` entry must be a plain string agent id. */
function isDependenciesShape(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((dep) => typeof dep === 'string')
}

/**
 * Each ``acceptance_criteria`` entry must be a non-null object with a
 * string ``description`` (the only field ``sanitizeTask`` reads). A
 * bare shape check here keeps ``sanitizeTask.ac.description`` safe
 * from malformed payloads smuggling non-string values.
 */
function isAcceptanceCriteriaShape(
  value: unknown,
): value is Array<{ description: string }> {
  if (!Array.isArray(value)) return false
  return value.every((ac) => {
    if (typeof ac !== 'object' || ac === null || Array.isArray(ac)) return false
    return typeof (ac as { description?: unknown }).description === 'string'
  })
}

function isTaskShape(c: Record<string, unknown>): c is Record<string, unknown> & Task {
  return (
    typeof c.id === 'string' &&
    typeof c.status === 'string' &&
    TASK_STATUS_SET.has(c.status) &&
    typeof c.title === 'string' &&
    typeof c.priority === 'string' &&
    TASK_PRIORITY_SET.has(c.priority) &&
    typeof c.type === 'string' &&
    TASK_TYPE_SET.has(c.type) &&
    isDependenciesShape(c.dependencies) &&
    isAcceptanceCriteriaShape(c.acceptance_criteria)
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
        get().upsertTask(sanitizeTask(candidate))
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
