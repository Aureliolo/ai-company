import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Drawer } from '@/components/ui/drawer'

// Mock framer-motion to avoid animation timing issues in tests
function MockAnimatePresence({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<typeof import('framer-motion')>('framer-motion')
  return {
    ...actual,
    AnimatePresence: MockAnimatePresence,
    motion: {
      div: ({
        children,
        className,
        role,
        'aria-modal': ariaModal,
        'aria-label': ariaLabel,
        tabIndex,
        onClick,
        'aria-hidden': ariaHidden,
        ...rest
      }: React.ComponentProps<'div'> & Record<string, unknown>) => (
        <div
          className={className}
          role={role}
          aria-modal={ariaModal}
          aria-label={ariaLabel}
          aria-hidden={ariaHidden}
          tabIndex={tabIndex}
          onClick={onClick}
          ref={rest.ref as React.Ref<HTMLDivElement>}
        >
          {children}
        </div>
      ),
    },
  }
})

describe('Drawer', () => {
  it('renders nothing when closed', () => {
    render(<Drawer open={false} onClose={() => {}} title="Test">Content</Drawer>)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders dialog when open', () => {
    render(<Drawer open={true} onClose={() => {}} title="Compare">Content</Drawer>)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('renders title', () => {
    render(<Drawer open={true} onClose={() => {}} title="Compare Templates">Content</Drawer>)
    expect(screen.getByText('Compare Templates')).toBeInTheDocument()
  })

  it('renders children', () => {
    render(
      <Drawer open={true} onClose={() => {}} title="Test">
        <p>Drawer content</p>
      </Drawer>,
    )
    expect(screen.getByText('Drawer content')).toBeInTheDocument()
  })

  it('has aria-modal attribute', () => {
    render(<Drawer open={true} onClose={() => {}} title="Test">Content</Drawer>)
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true')
  })

  it('has aria-label matching title', () => {
    render(<Drawer open={true} onClose={() => {}} title="Compare">Content</Drawer>)
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Compare')
  })

  it('calls onClose when close button is clicked', async () => {
    const handleClose = vi.fn()
    const user = userEvent.setup()
    render(<Drawer open={true} onClose={handleClose} title="Test">Content</Drawer>)
    await user.click(screen.getByLabelText('Close'))
    expect(handleClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when overlay is clicked', async () => {
    const handleClose = vi.fn()
    const user = userEvent.setup()
    render(<Drawer open={true} onClose={handleClose} title="Test">Content</Drawer>)
    // The overlay is the element with aria-hidden="true"
    const overlay = screen.getByRole('dialog').previousElementSibling
    expect(overlay).toBeInTheDocument()
    await user.click(overlay!)
    expect(handleClose).toHaveBeenCalledOnce()
  })

  it('calls onClose on Escape key', async () => {
    const handleClose = vi.fn()
    const user = userEvent.setup()
    render(<Drawer open={true} onClose={handleClose} title="Test">Content</Drawer>)
    await user.keyboard('{Escape}')
    expect(handleClose).toHaveBeenCalledOnce()
  })
})
