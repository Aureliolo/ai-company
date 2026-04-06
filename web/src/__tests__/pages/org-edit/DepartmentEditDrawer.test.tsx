import { render, screen } from '@testing-library/react'
import { DepartmentEditDrawer } from '@/pages/org-edit/DepartmentEditDrawer'
import { makeCompanyConfig, makeDepartment, makeDepartmentHealth } from '../../helpers/factories'

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

  it('renders Save and Delete buttons as enabled', () => {
    renderDrawer()
    const saveButton = screen.getByRole('button', { name: /save/i })
    const deptDelete = screen.getByTestId('dept-delete')
    expect(saveButton).not.toBeDisabled()
    expect(deptDelete).not.toBeDisabled()
  })
})
