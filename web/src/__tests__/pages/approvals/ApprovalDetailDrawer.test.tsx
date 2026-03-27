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
