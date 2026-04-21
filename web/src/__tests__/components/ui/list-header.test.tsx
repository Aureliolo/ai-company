import { render, screen } from '@testing-library/react'
import { Button } from '@/components/ui/button'
import { ListHeader } from '@/components/ui/list-header'

describe('ListHeader', () => {
  it('renders title as h1', () => {
    render(<ListHeader title="Agents" />)
    expect(screen.getByRole('heading', { level: 1, name: 'Agents' })).toBeInTheDocument()
  })

  it('renders formatted count when provided', () => {
    render(<ListHeader title="Tasks" count={12345} />)
    // count includes "12" and "345" separated by a locale-specific thousands separator
    expect(screen.getByText(/\(12.345\)/)).toBeInTheDocument()
  })

  it('does not render count when undefined', () => {
    const { container } = render(<ListHeader title="Tasks" />)
    expect(container.querySelector('[aria-label$="items"]')).toBeNull()
  })

  it('countLabel override replaces parenthesised count', () => {
    render(<ListHeader title="Tasks" count={5} countLabel="5 open, 10 closed" />)
    expect(screen.getByText('5 open, 10 closed')).toBeInTheDocument()
    expect(screen.queryByText('(5)')).not.toBeInTheDocument()
  })

  it('renders description', () => {
    render(<ListHeader title="T" description="List description" />)
    expect(screen.getByText('List description')).toBeInTheDocument()
  })

  it('renders primary action', () => {
    render(
      <ListHeader title="T" primaryAction={<Button>Create</Button>} />,
    )
    expect(screen.getByRole('button', { name: 'Create' })).toBeInTheDocument()
  })

  it('renders secondary actions', () => {
    render(
      <ListHeader
        title="T"
        secondaryActions={<span data-testid="secondary">filters</span>}
      />,
    )
    expect(screen.getByTestId('secondary')).toBeInTheDocument()
  })
})
