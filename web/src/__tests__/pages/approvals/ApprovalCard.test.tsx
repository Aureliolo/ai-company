import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import fc from 'fast-check'
import { ApprovalCard } from '@/pages/approvals/ApprovalCard'
import { makeApproval } from '../../helpers/factories'

const defaultHandlers = {
  onSelect: vi.fn(),
  onApprove: vi.fn(),
  onReject: vi.fn(),
  onToggleSelect: vi.fn(),
}

function renderCard(overrides: Parameters<typeof makeApproval>[1] = {}, selected = false) {
  const approval = makeApproval('test-1', {
    title: 'Deploy API',
    action_type: 'deploy:production',
    requested_by: 'agent-eng',
    risk_level: 'critical',
    seconds_remaining: 3600,
    urgency_level: 'critical',
    ...overrides,
  })
  return render(
    <ApprovalCard
      approval={approval}
      selected={selected}
      {...defaultHandlers}
    />,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ApprovalCard', () => {
  it('renders title and action type', () => {
    renderCard()
    expect(screen.getByText('Deploy API')).toBeInTheDocument()
    expect(screen.getByText('deploy:production')).toBeInTheDocument()
  })

  it('renders requester', () => {
    renderCard()
    expect(screen.getByText('agent-eng')).toBeInTheDocument()
  })

  it('renders urgency countdown for pending items', () => {
    renderCard({ seconds_remaining: 7200 })
    expect(screen.getByText('2h 0m')).toBeInTheDocument()
  })

  it('renders "No expiry" when no TTL', () => {
    renderCard({ seconds_remaining: null, urgency_level: 'no_expiry' })
    expect(screen.getByText('No expiry')).toBeInTheDocument()
  })

  it('shows approve/reject buttons for pending items', () => {
    renderCard()
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
  })

  it('hides approve/reject buttons for non-pending items', () => {
    renderCard({ status: 'approved' })
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /reject/i })).not.toBeInTheDocument()
  })

  it('shows checkbox for pending items', () => {
    renderCard()
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
  })

  it('hides checkbox for non-pending items', () => {
    renderCard({ status: 'rejected' })
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('calls onSelect when title is clicked', async () => {
    renderCard()
    await userEvent.click(screen.getByText('Deploy API'))
    expect(defaultHandlers.onSelect).toHaveBeenCalledWith('test-1')
  })

  it('calls onApprove when approve button is clicked', async () => {
    renderCard()
    await userEvent.click(screen.getByRole('button', { name: /approve/i }))
    expect(defaultHandlers.onApprove).toHaveBeenCalledWith('test-1')
  })

  it('calls onReject when reject button is clicked', async () => {
    renderCard()
    await userEvent.click(screen.getByRole('button', { name: /reject/i }))
    expect(defaultHandlers.onReject).toHaveBeenCalledWith('test-1')
  })

  it('calls onToggleSelect when checkbox is clicked', async () => {
    renderCard()
    await userEvent.click(screen.getByRole('checkbox'))
    expect(defaultHandlers.onToggleSelect).toHaveBeenCalledWith('test-1')
  })

  it('marks checkbox as checked when selected', () => {
    renderCard({}, true)
    expect(screen.getByRole('checkbox')).toBeChecked()
  })

  it('renders without crashing for any status/countdown/urgency (property)', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('pending' as const, 'approved' as const, 'rejected' as const, 'expired' as const),
        fc.option(fc.integer({ min: 0, max: 86400 }), { nil: null }),
        fc.constantFrom('critical' as const, 'high' as const, 'normal' as const, 'no_expiry' as const),
        (status, secondsRemaining, urgencyLevel) => {
          const { unmount } = renderCard({
            status,
            seconds_remaining: secondsRemaining,
            urgency_level: urgencyLevel,
          })
          if (status === 'pending') {
            expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
          } else {
            expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
          }
          unmount()
        },
      ),
      { numRuns: 20 },
    )
  })
})
