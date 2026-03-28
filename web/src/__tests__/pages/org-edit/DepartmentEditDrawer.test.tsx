import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DepartmentEditDrawer } from '@/pages/org-edit/DepartmentEditDrawer'
import { makeDepartment, makeDepartmentHealth } from '../../helpers/factories'

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

  beforeEach(() => vi.resetAllMocks())

  it('renders department info when open', () => {
    renderDrawer()
    expect(screen.getByText(/Edit: Engineering/)).toBeInTheDocument()
  })

  it('renders health bar when health is provided', () => {
    renderDrawer()
    expect(screen.getByRole('meter')).toBeInTheDocument()
  })

  it('renders without health bar when health is null', () => {
    renderDrawer({ health: null })
    expect(screen.queryByRole('meter')).not.toBeInTheDocument()
  })

  it('renders teams summary', () => {
    renderDrawer()
    expect(screen.getByText('Backend')).toBeInTheDocument()
    expect(screen.getByText(/2 members/)).toBeInTheDocument()
  })

  it('calls onUpdate when Save is clicked', async () => {
    renderDrawer()
    fireEvent.click(screen.getByText('Save'))
    await waitFor(() => {
      expect(mockOnUpdate).toHaveBeenCalledWith('engineering', expect.any(Object))
    })
  })

  it('opens confirmation dialog on Delete click', () => {
    renderDrawer()
    fireEvent.click(screen.getByText('Delete'))
    expect(screen.getByText('Delete Engineering?')).toBeInTheDocument()
  })

  it('calls onDelete with department name after confirming delete', async () => {
    renderDrawer()
    fireEvent.click(screen.getByText('Delete'))
    // Confirm in the dialog
    const confirmButtons = screen.getAllByText('Delete')
    fireEvent.click(confirmButtons[confirmButtons.length - 1]!)
    await waitFor(() => {
      expect(mockOnDelete).toHaveBeenCalledWith('engineering')
    })
  })

  it('sends budget_percent of 0 correctly (not undefined)', async () => {
    renderDrawer()
    // Budget default is '0' -- should send 0, not undefined
    fireEvent.click(screen.getByText('Save'))
    await waitFor(() => {
      expect(mockOnUpdate).toHaveBeenCalledWith('engineering', expect.objectContaining({
        budget_percent: 0,
      }))
    })
  })

  it('displays save error when onUpdate rejects', async () => {
    const failingOnUpdate = vi.fn().mockRejectedValue(new Error('Permission denied'))
    render(
      <DepartmentEditDrawer
        open={true}
        onClose={mockOnClose}
        department={dept}
        health={health}
        onUpdate={failingOnUpdate}
        onDelete={mockOnDelete}
        saving={false}
      />,
    )
    fireEvent.click(screen.getByText('Save'))
    await waitFor(() => {
      expect(screen.getByText('Permission denied')).toBeInTheDocument()
    })
  })
})
