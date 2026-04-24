import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BatchActionBar } from '@/pages/approvals/BatchActionBar'

const defaultProps = {
  selectedCount: 3,
  onApproveAll: vi.fn(),
  onRejectAll: vi.fn(),
  onClearSelection: vi.fn(),
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('BatchActionBar', () => {
  it('renders selected count', () => {
    render(<BatchActionBar {...defaultProps} />)
    expect(screen.getByText('3 selected')).toBeInTheDocument()
  })

  it('calls onApproveAll when Approve All is clicked', async () => {
    render(<BatchActionBar {...defaultProps} />)
    await userEvent.click(screen.getByRole('button', { name: /approve 3/i }))
    expect(defaultProps.onApproveAll).toHaveBeenCalledTimes(1)
  })

  it('calls onRejectAll when Reject All is clicked', async () => {
    render(<BatchActionBar {...defaultProps} />)
    await userEvent.click(screen.getByRole('button', { name: /reject 3/i }))
    expect(defaultProps.onRejectAll).toHaveBeenCalledTimes(1)
  })

  it('calls onClearSelection when Clear is clicked', async () => {
    render(<BatchActionBar {...defaultProps} />)
    await userEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(defaultProps.onClearSelection).toHaveBeenCalledTimes(1)
  })

  it('disables buttons when loading', () => {
    render(<BatchActionBar {...defaultProps} loading />)
    expect(screen.getByRole('button', { name: /approve 3/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /reject 3/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /clear/i })).toBeDisabled()
  })

  it('has toolbar role and accessible label', () => {
    render(<BatchActionBar {...defaultProps} />)
    expect(screen.getByRole('toolbar', { name: /batch actions/i })).toBeInTheDocument()
  })
})
