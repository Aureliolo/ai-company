import { render, screen } from '@testing-library/react'
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

  it('renders Save and Delete buttons as enabled', () => {
    renderDrawer()
    const saveButton = screen.getByRole('button', { name: /save/i })
    const deleteButton = screen.getByRole('button', { name: /delete/i })
    expect(saveButton).not.toBeDisabled()
    expect(deleteButton).not.toBeDisabled()
  })
})
