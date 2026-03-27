import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TaskCreateDialog } from '@/pages/tasks/TaskCreateDialog'

describe('TaskCreateDialog', () => {
  it('renders nothing when closed', () => {
    render(<TaskCreateDialog open={false} onOpenChange={() => {}} onCreate={async () => {}} />)
    expect(screen.queryByText('New Task')).not.toBeInTheDocument()
  })

  it('renders dialog when open', () => {
    render(<TaskCreateDialog open={true} onOpenChange={() => {}} onCreate={async () => {}} />)
    expect(screen.getByText('New Task')).toBeInTheDocument()
  })

  it('renders required form fields', () => {
    render(<TaskCreateDialog open={true} onOpenChange={() => {}} onCreate={async () => {}} />)
    expect(screen.getByPlaceholderText('Task title')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Describe the task...')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Project name')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Agent or user')).toBeInTheDocument()
  })

  it('shows validation errors for empty required fields', async () => {
    const user = userEvent.setup()
    render(<TaskCreateDialog open={true} onOpenChange={() => {}} onCreate={async () => {}} />)
    await user.click(screen.getByText('Create Task'))
    expect(screen.getByText('Title is required')).toBeInTheDocument()
    expect(screen.getByText('Description is required')).toBeInTheDocument()
    expect(screen.getByText('Project is required')).toBeInTheDocument()
    expect(screen.getByText('Creator is required')).toBeInTheDocument()
  })

  it('calls onCreate with form data on valid submission', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn().mockResolvedValue(undefined)
    render(<TaskCreateDialog open={true} onOpenChange={() => {}} onCreate={onCreate} />)

    await user.type(screen.getByPlaceholderText('Task title'), 'My task')
    await user.type(screen.getByPlaceholderText('Describe the task...'), 'Task description')
    await user.type(screen.getByPlaceholderText('Project name'), 'my-project')
    await user.type(screen.getByPlaceholderText('Agent or user'), 'agent-cto')

    await user.click(screen.getByText('Create Task'))

    expect(onCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'My task',
        description: 'Task description',
        project: 'my-project',
        created_by: 'agent-cto',
      }),
    )
  })

  it('shows error message on submission failure', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn().mockRejectedValue(new Error('Server error'))
    render(<TaskCreateDialog open={true} onOpenChange={() => {}} onCreate={onCreate} />)

    await user.type(screen.getByPlaceholderText('Task title'), 'My task')
    await user.type(screen.getByPlaceholderText('Describe the task...'), 'Desc')
    await user.type(screen.getByPlaceholderText('Project name'), 'proj')
    await user.type(screen.getByPlaceholderText('Agent or user'), 'agent')

    await user.click(screen.getByText('Create Task'))
    expect(screen.getByText('Server error')).toBeInTheDocument()
  })
})
