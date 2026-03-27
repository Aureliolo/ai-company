import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TaskCard } from '@/pages/tasks/TaskCard'
import type { Task } from '@/api/types'

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    title: 'Test task',
    description: 'A test task description',
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

describe('TaskCard', () => {
  it('renders task title', () => {
    render(<TaskCard task={makeTask()} onSelect={() => {}} />)
    expect(screen.getByText('Test task')).toBeInTheDocument()
  })

  it('renders description preview', () => {
    render(<TaskCard task={makeTask()} onSelect={() => {}} />)
    expect(screen.getByText('A test task description')).toBeInTheDocument()
  })

  it('renders assignee avatar when assigned_to is set', () => {
    render(<TaskCard task={makeTask()} onSelect={() => {}} />)
    expect(screen.getByLabelText('agent-eng')).toBeInTheDocument()
  })

  it('does not render avatar when assigned_to is null', () => {
    render(<TaskCard task={makeTask({ assigned_to: null })} onSelect={() => {}} />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('renders priority badge', () => {
    render(<TaskCard task={makeTask({ priority: 'critical' })} onSelect={() => {}} />)
    expect(screen.getByText('Critical')).toBeInTheDocument()
  })

  it('renders dependency count when dependencies exist', () => {
    render(<TaskCard task={makeTask({ dependencies: ['dep-1', 'dep-2'] })} onSelect={() => {}} />)
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('does not render dependency count when empty', () => {
    render(<TaskCard task={makeTask({ dependencies: [] })} onSelect={() => {}} />)
    expect(screen.queryByTitle(/dependencies/)).not.toBeInTheDocument()
  })

  it('calls onSelect when clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<TaskCard task={makeTask()} onSelect={onSelect} />)
    await user.click(screen.getByRole('button'))
    expect(onSelect).toHaveBeenCalledWith('task-1')
  })

  it('calls onSelect on Enter key', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<TaskCard task={makeTask()} onSelect={onSelect} />)
    const card = screen.getByRole('button')
    card.focus()
    await user.keyboard('{Enter}')
    expect(onSelect).toHaveBeenCalledWith('task-1')
  })

  it('has accessible label with task title', () => {
    render(<TaskCard task={makeTask({ title: 'My task' })} onSelect={() => {}} />)
    expect(screen.getByLabelText('Task: My task')).toBeInTheDocument()
  })
})
