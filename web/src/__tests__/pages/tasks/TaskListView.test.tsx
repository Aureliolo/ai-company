import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TaskListView } from '@/pages/tasks/TaskListView'
import { makeTask } from '../../helpers/factories'

describe('TaskListView', () => {
  const tasks = [
    makeTask('t1', 'First task', { status: 'in_progress' }),
    makeTask('t2', 'Second task', { status: 'completed', assigned_to: null }),
  ]

  it('renders table headers', () => {
    render(<TaskListView tasks={tasks} onSelectTask={() => {}} />)
    expect(screen.getByText('Status')).toBeInTheDocument()
    expect(screen.getByText('Title')).toBeInTheDocument()
    expect(screen.getByText('Assignee')).toBeInTheDocument()
    expect(screen.getByText('Priority')).toBeInTheDocument()
  })

  it('renders task rows', () => {
    render(<TaskListView tasks={tasks} onSelectTask={() => {}} />)
    expect(screen.getByText('First task')).toBeInTheDocument()
    expect(screen.getByText('Second task')).toBeInTheDocument()
  })

  it('shows Unassigned for tasks without assignee', () => {
    render(<TaskListView tasks={tasks} onSelectTask={() => {}} />)
    expect(screen.getByText('Unassigned')).toBeInTheDocument()
  })

  it('calls onSelectTask when row is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<TaskListView tasks={tasks} onSelectTask={onSelect} />)
    await user.click(screen.getByText('First task'))
    expect(onSelect).toHaveBeenCalledWith('t1')
  })

  it('renders empty state when no tasks', () => {
    render(<TaskListView tasks={[]} onSelectTask={() => {}} />)
    expect(screen.getByText('No tasks found')).toBeInTheDocument()
  })
})
