import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { UseTaskBoardDataReturn } from '@/hooks/useTaskBoardData'
import type { Task } from '@/api/types'

function makeTask(id: string, overrides: Partial<Task> = {}): Task {
  return {
    id,
    title: `Task ${id}`,
    description: 'Description',
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
    ...overrides,
  }
}

const defaultHookReturn: UseTaskBoardDataReturn = {
  tasks: [
    makeTask('t1', { status: 'assigned' }),
    makeTask('t2', { status: 'in_progress', title: 'Active task' }),
    makeTask('t3', { status: 'completed', title: 'Done task' }),
  ],
  selectedTask: null,
  total: 3,
  loading: false,
  loadingDetail: false,
  error: null,
  wsConnected: true,
  wsSetupError: null,
  fetchTask: vi.fn(),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  transitionTask: vi.fn(),
  cancelTask: vi.fn(),
  deleteTask: vi.fn(),
  optimisticTransition: vi.fn(() => () => {}),
}

let hookReturn = { ...defaultHookReturn }

const getTaskBoardData = vi.fn(() => hookReturn)
vi.mock('@/hooks/useTaskBoardData', () => {
  const hookName = 'useTaskBoardData'
  return { [hookName]: () => getTaskBoardData() }
})

async function renderBoard(initialEntries: string[] = ['/tasks']) {
  const { default: TaskBoardPage } = await import('@/pages/TaskBoardPage')
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <TaskBoardPage />
    </MemoryRouter>,
  )
}

describe('TaskBoardPage', () => {
  beforeEach(() => {
    hookReturn = { ...defaultHookReturn }
  })

  it('renders page heading', async () => {
    await renderBoard()
    expect(screen.getByText('Task Board')).toBeInTheDocument()
  })

  it('renders loading skeleton when loading with no data', async () => {
    hookReturn = { ...defaultHookReturn, loading: true, tasks: [], total: 0 }
    await renderBoard()
    expect(screen.getByLabelText('Loading task board')).toBeInTheDocument()
  })

  it('does not show skeleton when loading but data exists', async () => {
    hookReturn = { ...defaultHookReturn, loading: true }
    await renderBoard()
    expect(screen.getByText('Task Board')).toBeInTheDocument()
    expect(screen.queryByLabelText('Loading task board')).not.toBeInTheDocument()
  })

  it('renders filter bar', async () => {
    await renderBoard()
    expect(screen.getByLabelText('Filter by status')).toBeInTheDocument()
    expect(screen.getByLabelText('Filter by priority')).toBeInTheDocument()
  })

  it('renders task cards in board view', async () => {
    await renderBoard()
    expect(screen.getByText('Task t1')).toBeInTheDocument()
    expect(screen.getByText('Active task')).toBeInTheDocument()
    expect(screen.getByText('Done task')).toBeInTheDocument()
  })

  it('renders kanban columns', async () => {
    const { container } = await renderBoard()
    expect(container.querySelector('[data-column-id="ready"]')).toBeInTheDocument()
    expect(container.querySelector('[data-column-id="in_progress"]')).toBeInTheDocument()
    expect(container.querySelector('[data-column-id="done"]')).toBeInTheDocument()
  })

  it('renders New Task button', async () => {
    await renderBoard()
    expect(screen.getByText('New Task')).toBeInTheDocument()
  })

  it('shows error banner when error is set', async () => {
    hookReturn = { ...defaultHookReturn, error: 'Failed to load tasks' }
    await renderBoard()
    expect(screen.getByText('Failed to load tasks')).toBeInTheDocument()
  })

  it('shows WebSocket disconnect warning', async () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false }
    await renderBoard()
    expect(screen.getByText(/disconnected/i)).toBeInTheDocument()
  })

  it('shows custom wsSetupError', async () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false, wsSetupError: 'WS auth failed' }
    await renderBoard()
    expect(screen.getByText('WS auth failed')).toBeInTheDocument()
  })

  it('renders task count', async () => {
    await renderBoard()
    expect(screen.getByText('3 tasks')).toBeInTheDocument()
  })

  it('renders Show terminal checkbox', async () => {
    await renderBoard()
    expect(screen.getByText('Show terminal')).toBeInTheDocument()
  })
})
