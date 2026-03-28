import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DepartmentCreateDialog } from '@/pages/org-edit/DepartmentCreateDialog'

describe('DepartmentCreateDialog', () => {
  const mockOnCreate = vi.fn().mockResolvedValue({ name: 'design', display_name: 'Design', teams: [] })
  const mockOnOpenChange = vi.fn()

  function renderDialog(open = true, existingNames = ['engineering', 'product']) {
    return render(
      <DepartmentCreateDialog
        open={open}
        onOpenChange={mockOnOpenChange}
        existingNames={existingNames}
        onCreate={mockOnCreate}
      />,
    )
  }

  beforeEach(() => vi.resetAllMocks())

  it('renders form fields when open', () => {
    renderDialog()
    expect(screen.getByText('New Department')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. engineering')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. Engineering')).toBeInTheDocument()
  })

  it('shows validation errors for empty required fields', async () => {
    renderDialog()
    fireEvent.click(screen.getByText('Create Department'))
    expect(await screen.findByText('Name is required')).toBeInTheDocument()
    expect(screen.getByText('Display name is required')).toBeInTheDocument()
    expect(mockOnCreate).not.toHaveBeenCalled()
  })

  it('shows error for duplicate department name', async () => {
    renderDialog()
    fireEvent.change(screen.getByPlaceholderText('e.g. engineering'), { target: { value: 'Engineering' } })
    fireEvent.change(screen.getByPlaceholderText('e.g. Engineering'), { target: { value: 'Eng' } })
    fireEvent.click(screen.getByText('Create Department'))
    expect(await screen.findByText('Department already exists')).toBeInTheDocument()
  })

  it('calls onCreate with correct payload on valid submit', async () => {
    renderDialog()
    fireEvent.change(screen.getByPlaceholderText('e.g. engineering'), { target: { value: 'design' } })
    fireEvent.change(screen.getByPlaceholderText('e.g. Engineering'), { target: { value: 'Design' } })
    fireEvent.click(screen.getByText('Create Department'))

    await waitFor(() => {
      expect(mockOnCreate).toHaveBeenCalledWith({
        name: 'design',
        display_name: 'Design',
        budget_percent: 0,
      })
    })
  })

  it('shows error when onCreate fails', async () => {
    mockOnCreate.mockRejectedValueOnce(new Error('Conflict'))
    renderDialog()
    fireEvent.change(screen.getByPlaceholderText('e.g. engineering'), { target: { value: 'design' } })
    fireEvent.change(screen.getByPlaceholderText('e.g. Engineering'), { target: { value: 'Design' } })
    fireEvent.click(screen.getByText('Create Department'))
    expect(await screen.findByText('Conflict')).toBeInTheDocument()
  })
})
