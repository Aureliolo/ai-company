import { renderHook, act } from '@testing-library/react'
import { useTaskBoardData } from '@/hooks/useTaskBoardData'
import { useTasksStore } from '@/stores/tasks'

vi.mock('@/api/endpoints/tasks', () => ({
  listTasks: vi.fn().mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 }),
  getTask: vi.fn(),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  transitionTask: vi.fn(),
  cancelTask: vi.fn(),
  deleteTask: vi.fn(),
}))

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: vi.fn().mockReturnValue({
    connected: true,
    reconnectExhausted: false,
    setupError: null,
  }),
}))

vi.mock('@/hooks/usePolling', () => ({
  usePolling: vi.fn().mockReturnValue({
    active: false,
    error: null,
    start: vi.fn(),
    stop: vi.fn(),
  }),
}))

describe('useTaskBoardData', () => {
  beforeEach(() => {
    useTasksStore.setState({
      tasks: [],
      selectedTask: null,
      total: 0,
      loading: false,
      loadingDetail: false,
      error: null,
    })
  })

  it('returns store state after initial fetch', async () => {
    const { result } = renderHook(() => useTaskBoardData())
    // Wait for initial fetch effect to complete
    await act(async () => {})
    expect(result.current.tasks).toEqual([])
    expect(result.current.total).toBe(0)
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('returns WebSocket connection status', () => {
    const { result } = renderHook(() => useTaskBoardData())
    expect(result.current.wsConnected).toBe(true)
    expect(result.current.wsSetupError).toBeNull()
  })

  it('exposes store action references', () => {
    const { result } = renderHook(() => useTaskBoardData())
    expect(typeof result.current.fetchTask).toBe('function')
    expect(typeof result.current.createTask).toBe('function')
    expect(typeof result.current.updateTask).toBe('function')
    expect(typeof result.current.transitionTask).toBe('function')
    expect(typeof result.current.cancelTask).toBe('function')
    expect(typeof result.current.deleteTask).toBe('function')
    expect(typeof result.current.optimisticTransition).toBe('function')
  })

  it('triggers initial fetch on mount', async () => {
    const fetchTasks = vi.spyOn(useTasksStore.getState(), 'fetchTasks')
    renderHook(() => useTaskBoardData())
    // fetchTasks is called inside useEffect; we need to wait for it
    await act(async () => {})
    expect(fetchTasks).toHaveBeenCalled()
  })
})
