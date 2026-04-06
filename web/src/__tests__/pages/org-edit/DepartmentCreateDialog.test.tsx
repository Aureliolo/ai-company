import { render, screen } from '@testing-library/react'
import { DepartmentCreateDialog } from '@/pages/org-edit/DepartmentCreateDialog'

describe('DepartmentCreateDialog', () => {
  const mockOnOpenChange = vi.fn()
  const mockOnCreate = vi.fn().mockResolvedValue({ name: 'test', display_name: 'Test' })

  function renderDialog(open = true) {
    return render(
      <DepartmentCreateDialog
        open={open}
        onOpenChange={mockOnOpenChange}
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

  it('renders Create Department button as enabled', () => {
    renderDialog()
    const createButton = screen.getByRole('button', { name: /create department/i })
    expect(createButton).not.toBeDisabled()
  })
})
