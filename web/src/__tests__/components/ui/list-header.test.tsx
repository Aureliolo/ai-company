import { render, screen } from '@testing-library/react'
import fc from 'fast-check'
import { Button } from '@/components/ui/button'
import { ListHeader } from '@/components/ui/list-header'
import { formatNumber } from '@/utils/format'

describe('ListHeader', () => {
  it('renders title as h1', () => {
    render(<ListHeader title="Agents" />)
    expect(screen.getByRole('heading', { level: 1, name: 'Agents' })).toBeInTheDocument()
  })

  it('renders formatted count when provided', () => {
    render(<ListHeader title="Tasks" count={12345} />)
    expect(screen.getByText(`(${formatNumber(12345)})`)).toBeInTheDocument()
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

  it('property: countLabel always wins over count when both provided', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: -1_000, max: 1_000_000 }),
        // Constrain to a non-empty, visually-unique token so getByText can
        // match the rendered span without collisions with other UI text.
        fc.stringMatching(/^[A-Za-z0-9-]{3,12}$/),
        (count, countLabel) => {
          const { unmount } = render(
            <ListHeader title="T" count={count} countLabel={countLabel} />,
          )
          expect(screen.getByText(countLabel)).toBeInTheDocument()
          const formatted = `(${formatNumber(count)})`
          expect(screen.queryByText(formatted)).not.toBeInTheDocument()
          unmount()
        },
      ),
    )
  })
})
