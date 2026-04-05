import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

describe('ConfirmDialog', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    title: 'Delete agent?',
    onConfirm: vi.fn(),
  }

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('is not visible when open=false', () => {
    render(<ConfirmDialog {...defaultProps} open={false} />)
    expect(screen.queryByText('Delete agent?')).not.toBeInTheDocument()
  })

  it('is visible when open=true', () => {
    render(<ConfirmDialog {...defaultProps} />)
    expect(screen.getByText('Delete agent?')).toBeInTheDocument()
  })

  it('renders title and description', () => {
    render(
      <ConfirmDialog
        {...defaultProps}
        description="This action cannot be undone."
      />,
    )
    expect(screen.getByText('Delete agent?')).toBeInTheDocument()
    expect(screen.getByText('This action cannot be undone.')).toBeInTheDocument()
  })

  it('confirm button calls onConfirm', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(<ConfirmDialog {...defaultProps} onConfirm={onConfirm} />)

    await user.click(screen.getByRole('button', { name: /confirm/i }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('cancel button calls onOpenChange(false)', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    render(<ConfirmDialog {...defaultProps} onOpenChange={onOpenChange} />)

    await user.click(screen.getByRole('button', { name: /cancel/i }))
    // Base UI passes (open, eventDetails) to onOpenChange; we only assert on
    // the first argument since consumers only destructure `open`.
    expect(onOpenChange).toHaveBeenCalled()
    expect(onOpenChange.mock.calls[0]![0]).toBe(false)
  })

  it('uses custom confirm/cancel labels', () => {
    render(
      <ConfirmDialog
        {...defaultProps}
        confirmLabel="Yes, delete"
        cancelLabel="No, keep"
      />,
    )
    expect(screen.getByRole('button', { name: 'Yes, delete' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'No, keep' })).toBeInTheDocument()
  })

  it('destructive variant applies danger styling to confirm', () => {
    render(<ConfirmDialog {...defaultProps} variant="destructive" />)
    const confirmBtn = screen.getByRole('button', { name: /confirm/i })
    // Use the explicit data-variant attribute rather than a className
    // substring check -- the latter breaks if the Tailwind class scheme
    // changes even though the variant contract is preserved.
    expect(confirmBtn).toHaveAttribute('data-variant', 'destructive')
  })

  it('loading state disables both buttons', () => {
    render(<ConfirmDialog {...defaultProps} loading />)
    // Base UI renders internal focus-guard spans with role="button" to
    // implement its focus trap -- filter those out and only assert on the
    // real action buttons (Confirm + Cancel).
    const buttons = screen
      .getAllByRole('button')
      .filter((el) => !el.hasAttribute('data-base-ui-focus-guard'))
    expect(buttons).toHaveLength(2)
    for (const button of buttons) {
      expect(button).toBeDisabled()
    }
  })

  it('has role="alertdialog"', () => {
    render(<ConfirmDialog {...defaultProps} />)
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
  })
})
