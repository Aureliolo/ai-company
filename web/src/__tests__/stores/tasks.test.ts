import type { Task, WsEvent } from '@/api/types'
import { useTasksStore } from '@/stores/tasks'

const mockTask: Task = {
  id: 'task-1',
  title: 'Test task',
  description: 'A test task',
  type: 'development',
  status: 'assigned',
  priority: 'medium',
  project: 'test-project',
  created_by: 'agent-cto',
  assigned_to: 'agent-eng',
  reviewers: [],
  dependencies: [],
  artifacts_expected: [],
  acceptance_criteria: [],
  estimated_complexity: 'medium',
  budget_limit: 10,
  deadline: null,
  max_retries: 3,
  parent_task_id: null,
  delegation_chain: [],
  task_structure: null,
  coordination_topology: 'auto',
  version: 1,
}

const mockTask2: Task = { ...mockTask, id: 'task-2', title: 'Second task', status: 'in_progress' }

const mockListTasks = vi.fn()
const mockGetTask = vi.fn()
const mockCreateTask = vi.fn()
const mockUpdateTask = vi.fn()
const mockTransitionTask = vi.fn()
const mockCancelTask = vi.fn()
const mockDeleteTask = vi.fn()

vi.mock('@/api/endpoints/tasks', () => ({
  listTasks: (...args: unknown[]) => mockListTasks(...args),
  getTask: (...args: unknown[]) => mockGetTask(...args),
  createTask: (...args: unknown[]) => mockCreateTask(...args),
  updateTask: (...args: unknown[]) => mockUpdateTask(...args),
  transitionTask: (...args: unknown[]) => mockTransitionTask(...args),
  cancelTask: (...args: unknown[]) => mockCancelTask(...args),
  deleteTask: (...args: unknown[]) => mockDeleteTask(...args),
}))

function resetStore() {
  useTasksStore.setState({
    tasks: [],
    selectedTask: null,
    total: 0,
    loading: false,
    loadingDetail: false,
    error: null,
  })
}

describe('useTasksStore', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  // ── fetchTasks ──────────────────────────────────────────

  describe('fetchTasks', () => {
    it('sets loading to true during fetch', async () => {
      mockListTasks.mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 })
      const promise = useTasksStore.getState().fetchTasks()
      expect(useTasksStore.getState().loading).toBe(true)
      await promise
    })

    it('populates tasks on success', async () => {
      mockListTasks.mockResolvedValue({ data: [mockTask, mockTask2], total: 2, offset: 0, limit: 200 })
      await useTasksStore.getState().fetchTasks()
      const state = useTasksStore.getState()
      expect(state.tasks).toHaveLength(2)
      expect(state.total).toBe(2)
      expect(state.loading).toBe(false)
      expect(state.error).toBeNull()
    })

    it('passes filters to API', async () => {
      mockListTasks.mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 })
      await useTasksStore.getState().fetchTasks({ status: 'assigned', limit: 200 })
      expect(mockListTasks).toHaveBeenCalledWith({ status: 'assigned', limit: 200 })
    })

    it('sets error on failure', async () => {
      mockListTasks.mockRejectedValue(new Error('Network error'))
      await useTasksStore.getState().fetchTasks()
      const state = useTasksStore.getState()
      expect(state.loading).toBe(false)
      expect(state.error).toBe('Network error')
    })
  })

  // ── fetchTask ───────────────────────────────────────────

  describe('fetchTask', () => {
    it('sets loadingDetail during fetch', async () => {
      mockGetTask.mockResolvedValue(mockTask)
      const promise = useTasksStore.getState().fetchTask('task-1')
      expect(useTasksStore.getState().loadingDetail).toBe(true)
      await promise
    })

    it('sets selectedTask on success', async () => {
      mockGetTask.mockResolvedValue(mockTask)
      await useTasksStore.getState().fetchTask('task-1')
      expect(useTasksStore.getState().selectedTask).toEqual(mockTask)
      expect(useTasksStore.getState().loadingDetail).toBe(false)
    })

    it('sets error on failure', async () => {
      mockGetTask.mockRejectedValue(new Error('Not found'))
      await useTasksStore.getState().fetchTask('task-999')
      expect(useTasksStore.getState().loadingDetail).toBe(false)
      expect(useTasksStore.getState().error).toBe('Not found')
    })
  })

  // ── createTask ──────────────────────────────────────────

  describe('createTask', () => {
    it('prepends task to list and increments total', async () => {
      useTasksStore.setState({ tasks: [mockTask2], total: 1 })
      mockCreateTask.mockResolvedValue(mockTask)
      const result = await useTasksStore.getState().createTask({
        title: 'Test task',
        description: 'A test task',
        type: 'development',
        project: 'test-project',
        created_by: 'agent-cto',
      })
      expect(result).toEqual(mockTask)
      expect(useTasksStore.getState().tasks).toHaveLength(2)
      expect(useTasksStore.getState().tasks[0]!.id).toBe('task-1')
      expect(useTasksStore.getState().total).toBe(2)
    })

    it('propagates errors', async () => {
      mockCreateTask.mockRejectedValue(new Error('Validation failed'))
      await expect(useTasksStore.getState().createTask({
        title: 'T', description: 'D', type: 'development', project: 'p', created_by: 'a',
      })).rejects.toThrow('Validation failed')
    })
  })

  // ── updateTask ──────────────────────────────────────────

  describe('updateTask', () => {
    it('replaces task in list', async () => {
      const updated = { ...mockTask, title: 'Updated title' }
      useTasksStore.setState({ tasks: [mockTask, mockTask2], total: 2 })
      mockUpdateTask.mockResolvedValue(updated)
      const result = await useTasksStore.getState().updateTask('task-1', { title: 'Updated title' })
      expect(result.title).toBe('Updated title')
      expect(useTasksStore.getState().tasks[0]!.title).toBe('Updated title')
    })
  })

  // ── transitionTask ────────────────────────────────────

  describe('transitionTask', () => {
    it('updates task status in list', async () => {
      const transitioned = { ...mockTask, status: 'in_progress' as const }
      useTasksStore.setState({ tasks: [mockTask], total: 1 })
      mockTransitionTask.mockResolvedValue(transitioned)
      const result = await useTasksStore.getState().transitionTask('task-1', { target_status: 'in_progress' })
      expect(result.status).toBe('in_progress')
      expect(useTasksStore.getState().tasks[0]!.status).toBe('in_progress')
    })
  })

  // ── cancelTask ──────────────────────────────────────────

  describe('cancelTask', () => {
    it('updates task to cancelled', async () => {
      const cancelled = { ...mockTask, status: 'cancelled' as const }
      useTasksStore.setState({ tasks: [mockTask], total: 1 })
      mockCancelTask.mockResolvedValue(cancelled)
      const result = await useTasksStore.getState().cancelTask('task-1', { reason: 'No longer needed' })
      expect(result.status).toBe('cancelled')
    })
  })

  // ── deleteTask ──────────────────────────────────────────

  describe('deleteTask', () => {
    it('removes task from list and decrements total', async () => {
      useTasksStore.setState({ tasks: [mockTask, mockTask2], total: 2 })
      mockDeleteTask.mockResolvedValue(undefined)
      await useTasksStore.getState().deleteTask('task-1')
      expect(useTasksStore.getState().tasks).toHaveLength(1)
      expect(useTasksStore.getState().tasks[0]!.id).toBe('task-2')
      expect(useTasksStore.getState().total).toBe(1)
    })
  })

  // ── upsertTask ──────────────────────────────────────────

  describe('upsertTask', () => {
    it('inserts new task when not in list', () => {
      useTasksStore.setState({ tasks: [mockTask], total: 1 })
      useTasksStore.getState().upsertTask(mockTask2)
      expect(useTasksStore.getState().tasks).toHaveLength(2)
      expect(useTasksStore.getState().total).toBe(2)
    })

    it('replaces existing task by id', () => {
      const updated = { ...mockTask, title: 'New title' }
      useTasksStore.setState({ tasks: [mockTask, mockTask2], total: 2 })
      useTasksStore.getState().upsertTask(updated)
      expect(useTasksStore.getState().tasks).toHaveLength(2)
      expect(useTasksStore.getState().tasks[0]!.title).toBe('New title')
      expect(useTasksStore.getState().total).toBe(2) // total unchanged for update
    })
  })

  // ── removeTask ──────────────────────────────────────────

  describe('removeTask', () => {
    it('removes task by id and decrements total', () => {
      useTasksStore.setState({ tasks: [mockTask, mockTask2], total: 2 })
      useTasksStore.getState().removeTask('task-1')
      expect(useTasksStore.getState().tasks).toHaveLength(1)
      expect(useTasksStore.getState().total).toBe(1)
    })

    it('does not go below zero total', () => {
      useTasksStore.setState({ tasks: [], total: 0 })
      useTasksStore.getState().removeTask('nonexistent')
      expect(useTasksStore.getState().total).toBe(0)
    })
  })

  // ── optimisticTransition ──────────────────────────────

  describe('optimisticTransition', () => {
    it('updates task status and returns rollback function', () => {
      useTasksStore.setState({ tasks: [mockTask], total: 1 })
      const rollback = useTasksStore.getState().optimisticTransition('task-1', 'in_progress')
      expect(useTasksStore.getState().tasks[0]!.status).toBe('in_progress')

      rollback()
      expect(useTasksStore.getState().tasks[0]!.status).toBe('assigned')
    })

    it('returns no-op for nonexistent task', () => {
      useTasksStore.setState({ tasks: [mockTask], total: 1 })
      const rollback = useTasksStore.getState().optimisticTransition('nonexistent', 'in_progress')
      rollback() // should not throw
      expect(useTasksStore.getState().tasks[0]!.status).toBe('assigned')
    })
  })

  // ── handleWsEvent ─────────────────────────────────────

  describe('handleWsEvent', () => {
    it('upserts task from task.created event with full task payload', () => {
      const event: WsEvent = {
        event_type: 'task.created',
        channel: 'tasks',
        timestamp: new Date().toISOString(),
        payload: { task: mockTask },
      }
      useTasksStore.getState().handleWsEvent(event)
      expect(useTasksStore.getState().tasks).toHaveLength(1)
      expect(useTasksStore.getState().tasks[0]!.id).toBe('task-1')
    })

    it('upserts task from task.updated event', () => {
      useTasksStore.setState({ tasks: [mockTask], total: 1 })
      const updated = { ...mockTask, title: 'Updated via WS' }
      const event: WsEvent = {
        event_type: 'task.updated',
        channel: 'tasks',
        timestamp: new Date().toISOString(),
        payload: { task: updated },
      }
      useTasksStore.getState().handleWsEvent(event)
      expect(useTasksStore.getState().tasks[0]!.title).toBe('Updated via WS')
    })

    it('upserts task from task.status_changed event', () => {
      useTasksStore.setState({ tasks: [mockTask], total: 1 })
      const changed = { ...mockTask, status: 'completed' as const }
      const event: WsEvent = {
        event_type: 'task.status_changed',
        channel: 'tasks',
        timestamp: new Date().toISOString(),
        payload: { task: changed },
      }
      useTasksStore.getState().handleWsEvent(event)
      expect(useTasksStore.getState().tasks[0]!.status).toBe('completed')
    })

    it('ignores events without task payload', () => {
      const event: WsEvent = {
        event_type: 'task.created',
        channel: 'tasks',
        timestamp: new Date().toISOString(),
        payload: { some_other_field: 'value' },
      }
      useTasksStore.getState().handleWsEvent(event)
      expect(useTasksStore.getState().tasks).toHaveLength(0)
    })
  })
})
