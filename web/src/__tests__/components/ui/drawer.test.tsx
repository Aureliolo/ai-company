import React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Drawer } from '@/components/ui/drawer'

// Mock components defined at module level for ESLint compliance
function MockAnimatePresence({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

// React 19: ref is a regular prop, no forwardRef needed
function MockMotionDiv({ children, ref, ...allProps }: React.ComponentProps<'div'> & { ref?: React.Ref<HTMLDivElement> } & Record<string, unknown>) {
  const domProps = Object.fromEntries(
    Object.entries(allProps).filter(([key]) => !['variants', 'initial', 'animate', 'exit', 'transition'].includes(key)),
  ) as React.HTMLAttributes<HTMLDivElement>
  return <div ref={ref} {...domProps}>{children as React.ReactNode}</div>
}

// Test wrapper for focus-restore testing (needs state to toggle open/close)
function FocusRestoreWrapper() {
  const [open, setOpen] = React.useState(false)
  return (
    <>
      <button data-testid="opener" onClick={() => setOpen(true)}>Open</button>
      <Drawer open={open} onClose={() => setOpen(false)} title="Test">Content</Drawer>
    </>
  )
}

vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<typeof import('framer-motion')>('framer-motion')
  return {
    ...actual,
    AnimatePresence: MockAnimatePresence,
    motion: { div: MockMotionDiv },
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
    await user.click(screen.getByTestId('drawer-overlay'))
    expect(handleClose).toHaveBeenCalledOnce()
  })

  it('calls onClose on Escape key', async () => {
    const handleClose = vi.fn()
    const user = userEvent.setup()
    render(<Drawer open={true} onClose={handleClose} title="Test">Content</Drawer>)
    await user.keyboard('{Escape}')
    expect(handleClose).toHaveBeenCalledOnce()
  })

  it('restores focus to the opener element when closed', async () => {
    const user = userEvent.setup()
    render(<FocusRestoreWrapper />)
    const opener = screen.getByTestId('opener')

    // Focus the opener then open the drawer
    await user.click(opener)

    // Drawer is now open -- focus should have moved to the dialog panel
    const dialog = screen.getByRole('dialog')
    expect(document.activeElement).toBe(dialog)

    // Close the drawer by clicking the close button
    await user.click(screen.getByLabelText('Close'))

    // Focus should be restored to the opener
    expect(document.activeElement).toBe(opener)
  })

  describe('side prop', () => {
    it('renders on the left when side="left"', () => {
      render(<Drawer open={true} onClose={() => {}} title="Left" side="left">Content</Drawer>)
      const dialog = screen.getByRole('dialog')
      expect(dialog.className).toMatch(/left-0/)
      expect(dialog.className).not.toMatch(/right-0/)
    })

    it('renders on the right by default', () => {
      render(<Drawer open={true} onClose={() => {}} title="Right">Content</Drawer>)
      const dialog = screen.getByRole('dialog')
      expect(dialog.className).toMatch(/right-0/)
      expect(dialog.className).not.toMatch(/left-0/)
    })
  })

  describe('optional title (headerless mode)', () => {
    it('does not render header when title is omitted', () => {
      render(<Drawer open={true} onClose={() => {}} ariaLabel="Custom panel">Content</Drawer>)
      expect(screen.queryByLabelText('Close')).not.toBeInTheDocument()
      expect(screen.queryByRole('heading')).not.toBeInTheDocument()
    })

    it('uses ariaLabel for aria-label when title is omitted', () => {
      render(<Drawer open={true} onClose={() => {}} ariaLabel="Navigation menu">Content</Drawer>)
      expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Navigation menu')
    })

    it('ariaLabel takes precedence over title when both are provided', () => {
      render(<Drawer open={true} onClose={() => {}} title="Visible Title" ariaLabel="Screen Reader Label">Content</Drawer>)
      expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Screen Reader Label')
    })
  })

  describe('contentClassName', () => {
    it('merges contentClassName into the content wrapper', () => {
      render(
        <Drawer open={true} onClose={() => {}} title="Test" contentClassName="p-0">
          <span>Hello</span>
        </Drawer>,
      )
      const content = screen.getByTestId('drawer-content')
      expect(content.className).toMatch(/p-0/)
    })
  })
})
