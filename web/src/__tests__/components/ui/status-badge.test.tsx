import { render, screen } from '@testing-library/react'
import { StatusBadge } from '@/components/ui/status-badge'

describe('StatusBadge', () => {
  it('renders with active status color', () => {
    const { container } = render(<StatusBadge status="active" />)
    const dot = container.querySelector('[data-slot="status-dot"]')

    expect(dot).toHaveClass('bg-success')
  })

  it('renders with idle status color', () => {
    const { container } = render(<StatusBadge status="idle" />)
    const dot = container.querySelector('[data-slot="status-dot"]')

    expect(dot).toHaveClass('bg-accent')
  })

  it('renders with error status color', () => {
    const { container } = render(<StatusBadge status="error" />)
    const dot = container.querySelector('[data-slot="status-dot"]')

    expect(dot).toHaveClass('bg-danger')
  })

  it('renders with offline status color', () => {
    const { container } = render(<StatusBadge status="offline" />)
    const dot = container.querySelector('[data-slot="status-dot"]')

    expect(dot).toHaveClass('bg-text-secondary')
  })

  it('shows text label when label prop is true', () => {
    render(<StatusBadge status="active" label />)

    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('hides text label by default', () => {
    render(<StatusBadge status="active" />)

    expect(screen.queryByText('Active')).not.toBeInTheDocument()
  })

  it('always has aria-label regardless of visible label', () => {
    render(<StatusBadge status="error" />)

    expect(screen.getByLabelText('Error')).toBeInTheDocument()
  })

  it('applies pulse animation class when pulse prop is true', () => {
    const { container } = render(<StatusBadge status="active" pulse />)
    const dot = container.querySelector('[data-slot="status-dot"]')

    expect(dot).toHaveClass('animate-pulse')
  })

  it('does not apply pulse class by default', () => {
    const { container } = render(<StatusBadge status="active" />)
    const dot = container.querySelector('[data-slot="status-dot"]')

    expect(dot).not.toHaveClass('animate-pulse')
  })

  it('emits role="img" with aria-label for standalone use', () => {
    const { container } = render(<StatusBadge status="active" />)
    const wrapper = container.firstElementChild

    expect(wrapper).toHaveAttribute('role', 'img')
    expect(wrapper).toHaveAttribute('aria-label', 'Active')
  })

  it('uses aria-hidden when decorative is true', () => {
    const { container } = render(
      <StatusBadge status="active" decorative />,
    )
    const wrapper = container.firstElementChild

    expect(wrapper).toHaveAttribute('aria-hidden', 'true')
    expect(wrapper).not.toHaveAttribute('role')
    expect(wrapper).not.toHaveAttribute('aria-label')
  })

  it('decorative mode still preserves visible label when label prop is true', () => {
    render(<StatusBadge status="error" label decorative />)

    expect(screen.getByText('Error')).toBeInTheDocument()
  })

  it('announce mode sets role="status" and polite live region', () => {
    const { container } = render(
      <StatusBadge status="active" announce />,
    )
    const wrapper = container.firstElementChild

    expect(wrapper).toHaveAttribute('role', 'status')
    expect(wrapper).toHaveAttribute('aria-live', 'polite')
  })
})
