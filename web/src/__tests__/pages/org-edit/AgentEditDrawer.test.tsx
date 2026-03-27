import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AgentEditDrawer } from '@/pages/org-edit/AgentEditDrawer'
import { makeAgent, makeDepartment } from '../../helpers/factories'

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

  beforeEach(() => vi.clearAllMocks())

  it('renders agent info when open', () => {
    renderDrawer()
    expect(screen.getByText(/Edit: alice/)).toBeInTheDocument()
    expect(screen.getByDisplayValue('alice')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Lead Developer')).toBeInTheDocument()
  })

  it('calls onUpdate with form data when Save is clicked', async () => {
    renderDrawer()
    fireEvent.change(screen.getByDisplayValue('Lead Developer'), { target: { value: 'Senior Dev' } })
    fireEvent.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(mockOnUpdate).toHaveBeenCalledWith('alice', expect.objectContaining({
        role: 'Senior Dev',
      }))
    })
  })

  it('renders Delete button', () => {
    renderDrawer()
    expect(screen.getByText('Delete')).toBeInTheDocument()
  })

  it('opens confirmation dialog on Delete click', () => {
    renderDrawer()
    fireEvent.click(screen.getByText('Delete'))
    expect(screen.getByText('Delete alice?')).toBeInTheDocument()
  })

  it('shows model info as read-only', () => {
    renderDrawer()
    expect(screen.getByText(/test-provider/)).toBeInTheDocument()
    expect(screen.getByText(/test-medium-001/)).toBeInTheDocument()
  })
})
