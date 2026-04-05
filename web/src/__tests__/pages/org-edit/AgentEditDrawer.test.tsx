import { render, screen, fireEvent } from '@testing-library/react'
import { AgentEditDrawer } from '@/pages/org-edit/AgentEditDrawer'
import { makeAgent, makeDepartment } from '../../helpers/factories'

// Save + Delete are disabled while the backend CRUD endpoints are
// pending (#1081).  When the endpoints land, remove the
// "disables Save+Delete" test and restore the click-behaviour tests
// that were here previously -- see git history on this file.

describe('AgentEditDrawer', () => {
  const mockOnUpdate = vi.fn().mockResolvedValue(makeAgent('alice'))
  const mockOnDelete = vi.fn().mockResolvedValue(undefined)
  const mockOnClose = vi.fn()
  const agent = makeAgent('alice', { role: 'Lead Developer', level: 'lead' })
  const departments = [makeDepartment('engineering'), makeDepartment('product')]

  function renderDrawer(props?: { agent?: typeof agent | null; open?: boolean }) {
    return render(
      <AgentEditDrawer
        open={props?.open ?? true}
        onClose={mockOnClose}
        agent={props?.agent ?? agent}
        departments={departments}
        onUpdate={mockOnUpdate}
        onDelete={mockOnDelete}
        saving={false}
      />,
    )
  }

  beforeEach(() => vi.resetAllMocks())

  it('renders agent info when open', () => {
    renderDrawer()
    expect(screen.getByText(/Edit: alice/)).toBeInTheDocument()
    expect(screen.getByDisplayValue('alice')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Lead Developer')).toBeInTheDocument()
  })

  it('renders Delete button', () => {
    renderDrawer()
    expect(screen.getByText('Delete')).toBeInTheDocument()
  })

  it('shows model info as read-only', () => {
    renderDrawer()
    expect(screen.getByText(/test-provider/)).toBeInTheDocument()
    expect(screen.getByText(/test-medium-001/)).toBeInTheDocument()
  })

  it('disables Save and Delete buttons with #1081 tooltip', () => {
    renderDrawer()
    const saveButton = screen.getByRole('button', { name: /save/i })
    const deleteButton = screen.getByRole('button', { name: /delete/i })
    expect(saveButton).toBeDisabled()
    expect(deleteButton).toBeDisabled()
    expect(saveButton.getAttribute('title') ?? '').toContain('1081')
    expect(deleteButton.getAttribute('title') ?? '').toContain('1081')
    // Clicking the disabled buttons must not call the mutation props.
    fireEvent.click(saveButton)
    fireEvent.click(deleteButton)
    expect(mockOnUpdate).not.toHaveBeenCalled()
    expect(mockOnDelete).not.toHaveBeenCalled()
  })
})
