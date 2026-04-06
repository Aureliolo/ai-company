import { render, screen } from '@testing-library/react'
import { DepartmentCreateDialog } from '@/pages/org-edit/DepartmentCreateDialog'

// Create is disabled while the backend CRUD endpoints are pending
// (#1081).  When the endpoints land, remove the "disables Create"
// test and restore the submit/validation click-behaviour tests that
// were here previously -- see git history on this file.

describe('DepartmentCreateDialog', () => {
  const mockOnOpenChange = vi.fn()

  function renderDialog(open = true) {
    return render(
      <DepartmentCreateDialog
        open={open}
        onOpenChange={mockOnOpenChange}
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

  it('disables Create Department button with #1081 tooltip', () => {
    renderDialog()
    const createButton = screen.getByRole('button', { name: /create department/i })
    expect(createButton).toBeDisabled()
    expect(createButton.getAttribute('title') ?? '').toContain('1081')
  })
})
