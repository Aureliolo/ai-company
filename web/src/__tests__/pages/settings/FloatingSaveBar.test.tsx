import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FloatingSaveBar } from '@/pages/settings/FloatingSaveBar'

const defaultProps = {
  dirtyCount: 3,
  saving: false,
  onSave: vi.fn(),
  onDiscard: vi.fn(),
  saveError: null,
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('FloatingSaveBar', () => {
  it('renders with dirty count', () => {
    render(<FloatingSaveBar {...defaultProps} />)
    expect(screen.getByText('3 unsaved changes')).toBeInTheDocument()
  })

  it('renders singular form for 1 change', () => {
    render(<FloatingSaveBar {...defaultProps} dirtyCount={1} />)
    expect(screen.getByText('1 unsaved change')).toBeInTheDocument()
  })

  it('is hidden when dirtyCount is 0', () => {
    const { container } = render(<FloatingSaveBar {...defaultProps} dirtyCount={0} />)
    expect(screen.queryByText(/unsaved/)).not.toBeInTheDocument()
    // The ConfirmDialog is still mounted but not open, so only check for visible bar content
    expect(container.querySelector('[class*="sticky"]')).not.toBeInTheDocument()
  })

  it('save button calls onSave', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(<FloatingSaveBar {...defaultProps} onSave={onSave} />)

    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(onSave).toHaveBeenCalledOnce()
  })

  it('discard button opens ConfirmDialog', async () => {
    const user = userEvent.setup()
    render(<FloatingSaveBar {...defaultProps} />)

    await user.click(screen.getByRole('button', { name: /discard/i }))
    expect(screen.getByText('Discard changes?')).toBeInTheDocument()
  })

  it('confirming discard calls onDiscard', async () => {
    const user = userEvent.setup()
    const onDiscard = vi.fn()
    render(<FloatingSaveBar {...defaultProps} onDiscard={onDiscard} />)

    // Open discard dialog
    await user.click(screen.getByRole('button', { name: /discard/i }))
    // Confirm discard in the ConfirmDialog (confirmLabel is "Discard")
    await user.click(screen.getByRole('button', { name: /^discard$/i }))
    expect(onDiscard).toHaveBeenCalledOnce()
  })

  it('displays save error', () => {
    render(<FloatingSaveBar {...defaultProps} saveError="Failed to save settings" />)
    expect(screen.getByRole('alert')).toHaveTextContent('Failed to save settings')
  })

  it('disables buttons when saving', () => {
    render(<FloatingSaveBar {...defaultProps} saving />)
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /discard/i })).toBeDisabled()
  })
})
