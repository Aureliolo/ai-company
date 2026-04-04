import { create } from 'zustand'
import * as tasksApi from '@/api/endpoints/tasks'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import { createLogger } from '@/lib/logger'
import type {
  CancelTaskRequest,
  CreateTaskRequest,
  Task,
  TaskFilters,
  TaskStatus,
  TransitionTaskRequest,
  UpdateTaskRequest,
  WsEvent,
} from '@/api/types'

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

  // Actions
  fetchTasks: (filters?: TaskFilters) => Promise<void>
  fetchTask: (taskId: string) => Promise<void>
  createTask: (data: CreateTaskRequest) => Promise<Task>
  updateTask: (taskId: string, data: UpdateTaskRequest) => Promise<Task>
  transitionTask: (taskId: string, data: TransitionTaskRequest) => Promise<Task>
  cancelTask: (taskId: string, data: CancelTaskRequest) => Promise<Task>
  deleteTask: (taskId: string) => Promise<void>

  // Real-time
  handleWsEvent: (event: WsEvent) => void

  // Optimistic helpers
  pendingTransitions: Set<string>
  optimisticTransition: (taskId: string, targetStatus: TaskStatus) => () => void
  upsertTask: (task: Task) => void
  removeTask: (taskId: string) => void
}

const pendingTransitions = new Set<string>()

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
    const task = await tasksApi.createTask(data)
    set((s) => ({ tasks: [task, ...s.tasks], total: s.total + 1 }))
    return task
  },

  updateTask: async (taskId, data) => {
    const task = await tasksApi.updateTask(taskId, data)
    get().upsertTask(task)
    return task
  },

  transitionTask: async (taskId, data) => {
    const task = await tasksApi.transitionTask(taskId, data)
    get().upsertTask(task)
    return task
  },

  cancelTask: async (taskId, data) => {
    const task = await tasksApi.cancelTask(taskId, data)
    get().upsertTask(task)
    return task
  },

  deleteTask: async (taskId) => {
    await tasksApi.deleteTask(taskId)
    get().removeTask(taskId)
  },

  handleWsEvent: (event) => {
    const { payload } = event
    if (payload.task && typeof payload.task === 'object' && !Array.isArray(payload.task)) {
      const candidate = payload.task as Record<string, unknown>
      if (
        typeof candidate.id === 'string' &&
        typeof candidate.status === 'string' &&
        typeof candidate.title === 'string' &&
        typeof candidate.priority === 'string' &&
        typeof candidate.type === 'string' &&
        Array.isArray(candidate.dependencies) &&
        Array.isArray(candidate.acceptance_criteria)
      ) {
        if (pendingTransitions.has(candidate.id as string)) return
        get().upsertTask(candidate as unknown as Task)
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
