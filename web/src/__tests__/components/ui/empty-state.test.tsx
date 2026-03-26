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
})
