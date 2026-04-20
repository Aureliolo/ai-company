/**
 * Integration test: WebSocket event -> Tasks store update flow.
 *
 * Tests that WS events correctly update the tasks store state,
 * including optimistic transitions and conflict prevention.
 */
import { useTasksStore } from '@/stores/tasks'
import { makeTask } from '../helpers/factories'
import type { WsEvent } from '@/api/types/websocket'

describe('WS Tasks Integration', () => {
  afterEach(() => {
    // Ensure pendingTransitions is cleared even if a test fails mid-way
    // (the module-scoped Set in tasks.ts is not part of Zustand state)
    useTasksStore.getState().pendingTransitions.clear()
  })

  beforeEach(() => {
    useTasksStore.setState({
      tasks: [
        makeTask('task-1', 'First Task', { status: 'assigned' }),
        makeTask('task-2', 'Second Task', { status: 'in_progress' }),
      ],
      selectedTask: null,
      loading: false,
      loadingDetail: false,
      error: null,
    })
  })

  it('updates task status on task.status_changed WS event', () => {
    const event: WsEvent = {
      event_type: 'task.status_changed',
      channel: 'tasks',
      timestamp: new Date().toISOString(),
      payload: {
        task: makeTask('task-1', 'First Task', { status: 'in_progress', version: 2 }),
      },
    }

    useTasksStore.getState().handleWsEvent(event)

    const updated = useTasksStore.getState().tasks.find((t) => t.id === 'task-1')
    expect(updated?.status).toBe('in_progress')
  })

  it('adds new task on task.created WS event', () => {
    const event: WsEvent = {
      event_type: 'task.created',
      channel: 'tasks',
      timestamp: new Date().toISOString(),
      payload: {
        task: makeTask('task-3', 'New Task', { status: 'created', priority: 'high', version: 1 }),
      },
    }

    useTasksStore.getState().handleWsEvent(event)

    expect(useTasksStore.getState().tasks).toHaveLength(3)
    const newTask = useTasksStore.getState().tasks.find((t) => t.id === 'task-3')
    expect(newTask?.title).toBe('New Task')
  })

  it('skips WS update when optimistic transition is pending', () => {
    // Apply optimistic transition
    const rollback = useTasksStore.getState().optimisticTransition('task-1', 'completed')

    // Verify optimistic state
    const optimistic = useTasksStore.getState().tasks.find((t) => t.id === 'task-1')
    expect(optimistic?.status).toBe('completed')

    // WS event arrives with a different status -- should be skipped
    const event: WsEvent = {
      event_type: 'task.status_changed',
      channel: 'tasks',
      timestamp: new Date().toISOString(),
      payload: {
        task: makeTask('task-1', 'First Task', { status: 'in_review', version: 2 }),
      },
    }

    useTasksStore.getState().handleWsEvent(event)

    // Should still show optimistic value, not the WS value
    const afterWs = useTasksStore.getState().tasks.find((t) => t.id === 'task-1')
    expect(afterWs?.status).toBe('completed')

    // Rollback should restore original
    rollback()
    const afterRollback = useTasksStore.getState().tasks.find((t) => t.id === 'task-1')
    expect(afterRollback?.status).toBe('assigned')
  })
})
