import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApprovalDetailDrawer } from '@/pages/approvals/ApprovalDetailDrawer'
import { makeApproval } from '../../helpers/factories'
import { useToastStore } from '@/stores/toast'

// Mock components must be at module scope for eslint @eslint-react/component-hook-factories
function MockAnimatePresence({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function MockDiv(props: React.ComponentProps<'div'> & Record<string, unknown>) {
  return (
    <div className={props.className} onClick={props.onClick}>
      {props.children}
    </div>
  )
}

function MockAside(props: React.ComponentProps<'aside'> & Record<string, unknown>) {
  return (
    <aside
      className={props.className}
      role={props.role}
      aria-modal={props['aria-modal']}
      aria-label={props['aria-label']}
      ref={props.ref as React.Ref<HTMLElement>}
    >
      {props.children}
    </aside>
  )
}

// Mock framer-motion to avoid animation timing issues in tests
vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<typeof import('framer-motion')>('framer-motion')
  return {
    ...actual,
    AnimatePresence: MockAnimatePresence,
    motion: {
      div: MockDiv,
      aside: MockAside,
    },
  }
})

const defaultHandlers = {
  onClose: vi.fn(),
  onApprove: vi.fn<(id: string, data?: { comment?: string }) => Promise<void>>().mockResolvedValue(undefined),
  onReject: vi.fn<(id: string, data: { reason: string }) => Promise<void>>().mockResolvedValue(undefined),
}

function renderDrawer(
  overrides: Parameters<typeof makeApproval>[1] = {},
  props: Partial<React.ComponentProps<typeof ApprovalDetailDrawer>> = {},
) {
  const approval = makeApproval('test-1', {
    title: 'Deploy to production',
    description: 'Deploy API v2 to production cluster',
    action_type: 'deploy:production',
    requested_by: 'agent-eng',
    risk_level: 'critical',
    ...overrides,
  })
  return render(
    <ApprovalDetailDrawer
      approval={approval}
      open={true}
      {...defaultHandlers}
      {...props}
    />,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  useToastStore.setState({ toasts: [] })
})

describe('ApprovalDetailDrawer', () => {
  it('renders with approval data (title, description, risk level badge, status label)', () => {
    renderDrawer()
    expect(screen.getByText('Deploy to production')).toBeInTheDocument()
    expect(screen.getByText('Deploy API v2 to production cluster')).toBeInTheDocument()
    // "Critical" appears in both the risk badge and the metadata grid
    expect(screen.getAllByText('Critical').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Pending')).toBeInTheDocument()
  })

  it('shows loading spinner when loading is true and approval is null', () => {
    render(
      <ApprovalDetailDrawer
        approval={null}
        open={true}
        loading={true}
        {...defaultHandlers}
      />,
    )
    expect(screen.getByRole('status', { name: 'Loading approval' })).toBeInTheDocument()
  })

  it('shows error state when error prop is provided', () => {
    render(
      <ApprovalDetailDrawer
        approval={null}
        open={true}
        error="Failed to load approval"
        {...defaultHandlers}
      />,
    )
    expect(screen.getByText('Failed to load approval')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /close/i })).toBeInTheDocument()
  })

  it('error state hides stale approval content', () => {
    render(
      <ApprovalDetailDrawer
        approval={makeApproval('stale-1', { title: 'Stale approval title' })}
        open={true}
        error="Refetch failed"
        {...defaultHandlers}
      />,
    )
    expect(screen.getByText('Refetch failed')).toBeInTheDocument()
    expect(screen.queryByText('Stale approval title')).not.toBeInTheDocument()
  })

  it('close button calls onClose', async () => {
    const user = userEvent.setup()
    renderDrawer()
    await user.click(screen.getByRole('button', { name: /close panel/i }))
    expect(defaultHandlers.onClose).toHaveBeenCalledOnce()
  })

  it('Escape key calls onClose when no confirm dialog is open', async () => {
    const user = userEvent.setup()
    renderDrawer()
    await user.keyboard('{Escape}')
    expect(defaultHandlers.onClose).toHaveBeenCalledOnce()
  })

  it('approve button opens confirm dialog', async () => {
    const user = userEvent.setup()
    renderDrawer()
    await user.click(screen.getByRole('button', { name: /approve/i }))
    expect(screen.getByText('Approve Action')).toBeInTheDocument()
    expect(screen.getByText('Are you sure you want to approve this action?')).toBeInTheDocument()
  })

  it('reject button opens confirm dialog', async () => {
    const user = userEvent.setup()
    renderDrawer()
    await user.click(screen.getByRole('button', { name: /reject/i }))
    expect(screen.getByText('Reject Action')).toBeInTheDocument()
    expect(screen.getByText('Please provide a reason for rejection.')).toBeInTheDocument()
  })

  it('reject requires non-empty reason (shows toast error)', async () => {
    const user = userEvent.setup()
    renderDrawer()
    // Open reject dialog
    await user.click(screen.getByRole('button', { name: /reject/i }))
    // Click confirm without entering a reason
    await user.click(screen.getByRole('button', { name: /reject/i }))
    // Should show toast error -- onReject should NOT have been called
    expect(defaultHandlers.onReject).not.toHaveBeenCalled()
    const toasts = useToastStore.getState().toasts
    expect(toasts.some((t) => t.title === 'Please provide a rejection reason')).toBe(true)
  })

  it('renders conditional fields for decided approvals', () => {
    renderDrawer({
      status: 'approved',
      expires_at: '2026-04-01T00:00:00Z',
      seconds_remaining: 7200,
      decided_by: 'admin-user',
      decided_at: '2026-03-27T15:00:00Z',
      decision_reason: 'All checks passed',
      task_id: 'task-42',
      metadata: { region: 'eu-west', nested: { deep: true } as unknown as string },
    })
    expect(screen.getByText('Decided By')).toBeInTheDocument()
    expect(screen.getByText('admin-user')).toBeInTheDocument()
    expect(screen.getByText('Decided At')).toBeInTheDocument()
    expect(screen.getByText('Expires')).toBeInTheDocument()
    expect(screen.getByText('All checks passed')).toBeInTheDocument()
    expect(screen.getByText('task-42')).toBeInTheDocument()
    expect(screen.getByText('eu-west')).toBeInTheDocument()
    expect(screen.getByText('{"deep":true}')).toBeInTheDocument()
  })

  it('shows error toast when approve fails', async () => {
    const user = userEvent.setup()
    defaultHandlers.onApprove.mockRejectedValueOnce(new Error('Permission denied'))
    renderDrawer()
    await user.click(screen.getByRole('button', { name: /approve/i }))
    await user.click(screen.getByRole('button', { name: /approve/i }))
    const toasts = useToastStore.getState().toasts
    expect(toasts.some((t) => t.title === 'Failed to approve')).toBe(true)
  })

  it('shows error toast when reject fails', async () => {
    const user = userEvent.setup()
    defaultHandlers.onReject.mockRejectedValueOnce(new Error('Server error'))
    renderDrawer()
    await user.click(screen.getByRole('button', { name: /reject/i }))
    await user.type(screen.getByLabelText('Rejection reason'), 'Not needed')
    await user.click(screen.getByRole('button', { name: /reject/i }))
    const toasts = useToastStore.getState().toasts
    expect(toasts.some((t) => t.title === 'Failed to reject')).toBe(true)
  })

  it('successful approve submits with comment', async () => {
    const user = userEvent.setup()
    renderDrawer()
    await user.click(screen.getByRole('button', { name: /approve/i }))
    await user.type(screen.getByLabelText('Approval comment'), 'Looks good')
    await user.click(screen.getByRole('button', { name: /approve/i }))
    expect(defaultHandlers.onApprove).toHaveBeenCalledWith('test-1', { comment: 'Looks good' })
  })

  it('successful reject submits with reason', async () => {
    const user = userEvent.setup()
    renderDrawer()
    await user.click(screen.getByRole('button', { name: /reject/i }))
    await user.type(screen.getByLabelText('Rejection reason'), 'Missing documentation')
    await user.click(screen.getByRole('button', { name: /reject/i }))
    expect(defaultHandlers.onReject).toHaveBeenCalledWith('test-1', { reason: 'Missing documentation' })
  })

  it('Escape does not close drawer when confirm dialog is open', async () => {
    const user = userEvent.setup()
    renderDrawer()
    // Open approve confirm dialog
    await user.click(screen.getByRole('button', { name: /approve/i }))
    expect(screen.getByText('Approve Action')).toBeInTheDocument()
    // Escape closes the Radix AlertDialog but should NOT close the drawer
    await user.keyboard('{Escape}')
    expect(defaultHandlers.onClose).not.toHaveBeenCalled()
    // Drawer itself is still mounted
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('focus is trapped within the drawer', async () => {
    const user = userEvent.setup()
    renderDrawer()
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')

    const focusableElements = dialog.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    )
    expect(focusableElements.length).toBeGreaterThan(1)
    const first = focusableElements[0]!
    const last = focusableElements[focusableElements.length - 1]!

    // Tab forward past last element wraps to first
    last.focus()
    expect(document.activeElement).toBe(last)
    await user.tab()
    expect(document.activeElement).toBe(first)

    // Shift+Tab from first element wraps to last
    await user.tab({ shift: true })
    expect(document.activeElement).toBe(last)
  })

  it('renders nothing when open is false', () => {
    render(
      <ApprovalDetailDrawer
        approval={null}
        open={false}
        {...defaultHandlers}
      />,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('hides approve/reject buttons for non-pending approvals', () => {
    renderDrawer({ status: 'approved' })
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /reject/i })).not.toBeInTheDocument()
  })
})
