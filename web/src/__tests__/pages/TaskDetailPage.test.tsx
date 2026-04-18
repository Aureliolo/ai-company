import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { useTasksStore } from '@/stores/tasks'
import type { Task } from '@/api/types'

const mockGetTask = vi.fn()

vi.mock('@/api/endpoints/tasks', () => ({
  listTasks: vi.fn().mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 }),
  getTask: (...args: unknown[]) => mockGetTask(...args),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  transitionTask: vi.fn(),
  cancelTask: vi.fn(),
  deleteTask: vi.fn(),
}))

const mockTask: Task = {
  id: 'task-1',
  title: 'Test task',
  description: 'Test description',
  type: 'development',
  status: 'in_progress',
  priority: 'high',
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
  created_at: '2026-03-20T10:00:00Z',
  updated_at: '2026-03-25T14:00:00Z',
}

function resetStore(overrides: Partial<{ selectedTask: Task | null; loadingDetail: boolean; error: string | null }> = {}) {
  useTasksStore.setState({
    tasks: [],
    selectedTask: null,
    total: 0,
    loading: false,
    loadingDetail: false,
    error: null,
    ...overrides,
  })
}

async function renderDetailPage() {
  const { default: TaskDetailPage } = await import('@/pages/TaskDetailPage')
  return render(
    <MemoryRouter initialEntries={['/tasks/task-1']}>
      <Routes>
        <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
        <Route path="/tasks" element={<div>Board</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('TaskDetailPage', () => {
  // Controllable pending promises let loading-state tests simulate an
  // in-flight fetch without leaving a never-settled promise past teardown.
  // Each test appends its pending resolver to this list; afterEach
  // resolves them all so --detect-async-leaks sees a clean slate.
  const pendingResolvers: Array<() => void> = []
  function pendingPromise<T>(): Promise<T> {
    return new Promise<T>((resolve) => {
      pendingResolvers.push(() => resolve(undefined as T))
    })
  }

  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
    mockGetTask.mockResolvedValue(mockTask)
  })

  afterEach(() => {
    while (pendingResolvers.length > 0) {
      pendingResolvers.pop()?.()
    }
  })

  it('renders loading spinner when loadingDetail is true', async () => {
    mockGetTask.mockReturnValue(pendingPromise())
    resetStore({ loadingDetail: true })
    await renderDetailPage()
    expect(screen.queryByText('Test task')).not.toBeInTheDocument()
  })

  it('renders loading spinner when task is null', async () => {
    mockGetTask.mockReturnValue(pendingPromise())
    resetStore({ selectedTask: null, loadingDetail: false })
    await renderDetailPage()
    // Should show spinner since task is null (fetch is pending)
    expect(screen.queryByText('Test task')).not.toBeInTheDocument()
  })

  it('renders error message when fetch fails', async () => {
    mockGetTask.mockRejectedValue(new Error('Task not found'))
    await renderDetailPage()
    expect(await screen.findByText('Task not found')).toBeInTheDocument()
  })

  it('renders task details when task is loaded', async () => {
    await renderDetailPage()
    expect(await screen.findByText('Test task')).toBeInTheDocument()
    expect(screen.getByText('Test description')).toBeInTheDocument()
  })

  it('renders Back to Board button', async () => {
    await renderDetailPage()
    expect(await screen.findByText('Back to Board')).toBeInTheDocument()
  })

  it('renders transition buttons for in_progress task', async () => {
    await renderDetailPage()
    expect(await screen.findByRole('button', { name: 'In Review' })).toBeInTheDocument()
  })

  it('renders Delete button', async () => {
    await renderDetailPage()
    expect(await screen.findByRole('button', { name: 'Delete' })).toBeInTheDocument()
  })

  it('renders Cancel Task button for non-terminal tasks', async () => {
    await renderDetailPage()
    expect(await screen.findByRole('button', { name: 'Cancel Task' })).toBeInTheDocument()
  })

  it('does not render Cancel Task button for completed tasks', async () => {
    mockGetTask.mockResolvedValue({ ...mockTask, status: 'completed' })
    await renderDetailPage()
    await waitFor(() => expect(screen.getByText('Test task')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Cancel Task' })).not.toBeInTheDocument()
  })
})
