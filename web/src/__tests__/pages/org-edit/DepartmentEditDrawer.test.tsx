import { render, screen, fireEvent } from '@testing-library/react'
import { DepartmentEditDrawer } from '@/pages/org-edit/DepartmentEditDrawer'
import { makeCompanyConfig, makeDepartment, makeDepartmentHealth } from '../../helpers/factories'

// Save + Delete are disabled while the backend CRUD endpoints are
// pending (#1081).  When the endpoints land, remove the
// "disables Save+Delete" test and restore the click-behaviour tests
// that were here previously -- see git history on this file.

const noopAsync = vi.fn().mockResolvedValue(undefined)

describe('DepartmentEditDrawer', () => {
  const dept = makeDepartment('engineering', {
    teams: [{ name: 'Backend', lead: 'alice', members: ['alice', 'bob'] }],
  })
  const health = makeDepartmentHealth('engineering')
  const config = makeCompanyConfig()
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
        config={config}
        onUpdate={mockOnUpdate}
        onDelete={mockOnDelete}
        onCreateTeam={noopAsync}
        onUpdateTeam={noopAsync}
        onDeleteTeam={noopAsync}
        onReorderTeams={noopAsync}
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

  it('renders teams section with team cards', () => {
    renderDrawer()
    expect(screen.getByText('Backend')).toBeInTheDocument()
    expect(screen.getByText('Add Team')).toBeInTheDocument()
  })

  it('disables Save and dept Delete buttons with #1081 tooltip', () => {
    renderDrawer()
    const saveButton = screen.getByRole('button', { name: /^save$/i })
    // Department-level delete button (distinguished from team delete icons)
    const deptDeleteButtons = screen.getAllByRole('button', { name: /delete/i })
    const deptDelete = deptDeleteButtons.find(
      (btn) => btn.textContent?.toLowerCase().includes('delete') && btn.getAttribute('title')?.includes('1081'),
    )
    expect(saveButton).toBeDisabled()
    expect(deptDelete).toBeDefined()
    expect(deptDelete).toBeDisabled()
    expect(saveButton.getAttribute('title') ?? '').toContain('1081')
    // Clicking the disabled buttons must not call the mutation props.
    fireEvent.click(saveButton)
    if (deptDelete) fireEvent.click(deptDelete)
    expect(mockOnUpdate).not.toHaveBeenCalled()
    expect(mockOnDelete).not.toHaveBeenCalled()
  })
})
