import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AnimatePresence } from 'motion/react'
import { BulkActionBar } from '@/components/ui/bulk-action-bar'

type BarProps = Partial<React.ComponentProps<typeof BulkActionBar>>

function renderBar(props: BarProps = {}) {
  const {
    selectedCount = 3,
    onClear = vi.fn(),
    children = <button type="button">Delete 3</button>,
    ...rest
  } = props
  return render(
    <AnimatePresence>
      <BulkActionBar
        key="bulk-action-bar"
        selectedCount={selectedCount}
        onClear={onClear}
        {...rest}
      >
        {children}
      </BulkActionBar>
    </AnimatePresence>,
  )
}

describe('BulkActionBar', () => {
  it('renders the selected count', () => {
    renderBar({ selectedCount: 3 })
    expect(screen.getByText('3 selected')).toBeInTheDocument()
  })

  it('formats the selected count via the localised number formatter', () => {
    renderBar({ selectedCount: 1234 })
    // Default locale fallback is plain "en"; Intl formats 1234 as "1,234".
    expect(screen.getByText(/1[,.\s]?234 selected/)).toBeInTheDocument()
  })

  it('renders the caller-supplied action slot', () => {
    renderBar({ children: <button type="button">Delete 5</button> })
    expect(screen.getByRole('button', { name: 'Delete 5' })).toBeInTheDocument()
  })

  it('calls onClear when the Clear button is pressed', async () => {
    const onClear = vi.fn()
    const user = userEvent.setup()
    renderBar({ onClear })
    await user.click(screen.getByRole('button', { name: /clear/i }))
    expect(onClear).toHaveBeenCalledOnce()
  })

  it('disables the Clear button when loading', () => {
    renderBar({ loading: true })
    expect(screen.getByRole('button', { name: /clear/i })).toBeDisabled()
  })

  it('wires the toolbar role + accessible name', () => {
    renderBar({ ariaLabel: 'Workflow bulk actions' })
    expect(
      screen.getByRole('toolbar', { name: 'Workflow bulk actions' }),
    ).toBeInTheDocument()
  })

  it('falls back to "Bulk actions" aria-label when ariaLabel is omitted', () => {
    renderBar()
    expect(screen.getByRole('toolbar', { name: 'Bulk actions' })).toBeInTheDocument()
  })

  it('marks the count region as polite live', () => {
    renderBar({ selectedCount: 7 })
    const count = screen.getByText('7 selected')
    expect(count).toHaveAttribute('aria-live', 'polite')
  })
})
