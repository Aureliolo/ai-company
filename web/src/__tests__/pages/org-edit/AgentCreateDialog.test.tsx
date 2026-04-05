import { render, screen, fireEvent } from '@testing-library/react'
import { AgentCreateDialog } from '@/pages/org-edit/AgentCreateDialog'
import { makeDepartment } from '../../helpers/factories'

// Create is disabled while the backend CRUD endpoints are pending
// (#1081).  When the endpoints land, remove the "disables Create"
// test and restore the submit/validation click-behaviour tests that
// were here previously -- see git history on this file.

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

  beforeEach(() => vi.resetAllMocks())

  it('renders form fields when open', () => {
    renderDialog()
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/role/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/department/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/level/i)).toBeInTheDocument()
  })

  it('disables Create Agent button with #1081 tooltip', () => {
    renderDialog()
    const createButton = screen.getByRole('button', { name: /create agent/i })
    expect(createButton).toBeDisabled()
    expect(createButton.getAttribute('title') ?? '').toContain('1081')
    // Clicking the disabled button must not call onCreate.
    fireEvent.click(createButton)
    expect(mockOnCreate).not.toHaveBeenCalled()
  })

  it('does not render when closed', () => {
    renderDialog(false)
    expect(screen.queryByText('New Agent')).not.toBeInTheDocument()
  })
})
