import { render, screen, fireEvent } from '@testing-library/react'
import { DepartmentEditDrawer } from '@/pages/org-edit/DepartmentEditDrawer'
import { makeDepartment, makeDepartmentHealth } from '../../helpers/factories'

// Save + Delete are disabled while the backend CRUD endpoints are
// pending (#1081).  When the endpoints land, remove the
// "disables Save+Delete" test and restore the click-behaviour tests
// that were here previously -- see git history on this file.

describe('DepartmentEditDrawer', () => {
  const dept = makeDepartment('engineering', {
    teams: [{ name: 'Backend', members: ['alice', 'bob'] }],
  })
  const health = makeDepartmentHealth('engineering')
  const mockOnUpdate = vi.fn().mockResolvedValue(dept)
  const mockOnDelete = vi.fn().mockResolvedValue(undefined)
  const mockOnClose = vi.fn()

  function renderDrawer(props?: { department?: typeof dept | null; health?: typeof health | null }) {
    const resolvedHealth = props && 'health' in props ? (props.health ?? null) : health
    return render(
      <DepartmentEditDrawer
        open={true}
        onClose={mockOnClose}
        department={props?.department ?? dept}
        health={resolvedHealth}
        onUpdate={mockOnUpdate}
        onDelete={mockOnDelete}
        saving={false}
      />,
    )
  }

  beforeEach(() => vi.clearAllMocks())

  it('renders department info when open', () => {
    renderDrawer()
    expect(screen.getByText(/Edit: Engineering/)).toBeInTheDocument()
  })

  it('shows the agent count from the runtime health payload', () => {
    // The runtime utilisation gauge was removed from the editor -- the
    // drawer now shows a plain "N agent(s)" summary derived from the
    // health payload's agent_count field instead of a meter.
    renderDrawer()
    expect(screen.getByText(/3\s+agent/i)).toBeInTheDocument()
    expect(screen.queryByRole('meter')).not.toBeInTheDocument()
  })

  it('renders without a meter regardless of whether health is provided', () => {
    renderDrawer({ health: null })
    expect(screen.queryByRole('meter')).not.toBeInTheDocument()
  })

  it('renders teams summary', () => {
    renderDrawer()
    expect(screen.getByText('Backend')).toBeInTheDocument()
    expect(screen.getByText(/2 members/)).toBeInTheDocument()
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
