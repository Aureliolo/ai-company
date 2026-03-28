import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AgentCreateDialog } from '@/pages/org-edit/AgentCreateDialog'
import { makeDepartment } from '../../helpers/factories'

describe('AgentCreateDialog', () => {
  const mockOnCreate = vi.fn().mockResolvedValue({ id: 'new-agent', name: 'test' })
  const mockOnOpenChange = vi.fn()
  const departments = [makeDepartment('engineering'), makeDepartment('product')]

  function renderDialog(open = true) {
    return render(
      <AgentCreateDialog
        open={open}
        onOpenChange={mockOnOpenChange}
        departments={departments}
        onCreate={mockOnCreate}
      />,
    )
  }

  beforeEach(() => vi.clearAllMocks())

  it('renders form fields when open', () => {
    renderDialog()
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/role/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/department/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/level/i)).toBeInTheDocument()
  })

  it('shows validation errors for empty required fields', async () => {
    renderDialog()
    fireEvent.click(screen.getByText('Create Agent'))
    expect(await screen.findByText('Name is required')).toBeInTheDocument()
    expect(screen.getByText('Role is required')).toBeInTheDocument()
    expect(screen.getByText('Department is required')).toBeInTheDocument()
    expect(mockOnCreate).not.toHaveBeenCalled()
  })

  it('calls onCreate with correct payload on valid submit', async () => {
    renderDialog()
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText(/role/i), { target: { value: 'Developer' } })
    fireEvent.change(screen.getByLabelText(/department/i), { target: { value: 'engineering' } })
    fireEvent.click(screen.getByText('Create Agent'))

    await waitFor(() => {
      expect(mockOnCreate).toHaveBeenCalledWith({
        name: 'alice',
        role: 'Developer',
        department: 'engineering',
        level: 'mid',
      })
    })
  })

  it('shows error when onCreate fails', async () => {
    mockOnCreate.mockRejectedValueOnce(new Error('Server error'))
    renderDialog()
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText(/role/i), { target: { value: 'Dev' } })
    fireEvent.change(screen.getByLabelText(/department/i), { target: { value: 'engineering' } })
    fireEvent.click(screen.getByText('Create Agent'))

    expect(await screen.findByText('Server error')).toBeInTheDocument()
  })

  it('does not render when closed', () => {
    renderDialog(false)
    expect(screen.queryByText('New Agent')).not.toBeInTheDocument()
  })
})
