import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Search } from 'lucide-react'
import { EmptyState } from '@/components/ui/empty-state'

describe('EmptyState', () => {
  it('renders title', () => {
    render(<EmptyState title="No agents found" />)
    expect(screen.getByText('No agents found')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(
      <EmptyState title="No agents" description="Create your first agent to get started." />,
    )
    expect(screen.getByText('Create your first agent to get started.')).toBeInTheDocument()
  })

  it('renders icon when provided', () => {
    const { container } = render(<EmptyState title="No results" icon={Search} />)
    // Lucide icons render as SVG
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('does not render icon when not provided', () => {
    const { container } = render(<EmptyState title="Empty" />)
    expect(container.querySelector('svg')).not.toBeInTheDocument()
  })

  it('renders action button when provided', () => {
    const onClick = vi.fn()
    render(
      <EmptyState
        title="No agents"
        action={{ label: 'Create Agent', onClick }}
      />,
    )
    expect(screen.getByRole('button', { name: 'Create Agent' })).toBeInTheDocument()
  })

  it('action button onClick fires', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(
      <EmptyState
        title="No agents"
        action={{ label: 'Create Agent', onClick }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Create Agent' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not render action button when not provided', () => {
    render(<EmptyState title="Empty" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('applies className', () => {
    const { container } = render(<EmptyState title="Empty" className="min-h-64" />)
    expect(container.firstChild).toHaveClass('min-h-64')
  })

  it('uses centered layout', () => {
    const { container } = render(<EmptyState title="Empty" />)
    expect(container.firstChild).toHaveClass('flex', 'items-center', 'justify-center')
  })

  it('renders learnMore link with default label', () => {
    render(
      <EmptyState
        title="No rules"
        learnMore={{ href: 'https://example.com/docs' }}
      />,
    )
    expect(screen.getByRole('link', { name: /Learn more/i })).toHaveAttribute('href', 'https://example.com/docs')
  })

  it('learnMore respects custom label', () => {
    render(
      <EmptyState
        title="No rules"
        learnMore={{ label: 'See the guide', href: 'https://example.com/guide' }}
      />,
    )
    expect(screen.getByRole('link', { name: 'See the guide' })).toBeInTheDocument()
  })

  it('external learnMore opens in new tab', () => {
    render(
      <EmptyState
        title="Empty"
        learnMore={{ href: 'https://example.com', external: true }}
      />,
    )
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  it('internal learnMore does not set target=_blank', () => {
    render(
      <EmptyState
        title="Empty"
        learnMore={{ href: '/docs/custom-rules' }}
      />,
    )
    const link = screen.getByRole('link')
    expect(link).not.toHaveAttribute('target')
  })

  it('does not render learnMore link for unsafe href protocols', () => {
    render(
      <EmptyState
        title="Unsafe"
        learnMore={{ href: 'javascript:alert(1)' }}
      />,
    )
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('does not render learnMore link for data: URIs', () => {
    render(
      <EmptyState
        title="Unsafe"
        learnMore={{ href: 'data:text/html,<script>alert(1)</script>' }}
      />,
    )
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})
