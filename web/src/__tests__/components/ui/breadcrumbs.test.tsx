import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { Breadcrumbs } from '@/components/ui/breadcrumbs'

function renderBreadcrumbs(props: Parameters<typeof Breadcrumbs>[0]) {
  return render(
    <MemoryRouter>
      <Breadcrumbs {...props} />
    </MemoryRouter>,
  )
}

describe('Breadcrumbs', () => {
  it('renders nothing for empty items', () => {
    const { container } = renderBreadcrumbs({ items: [] })
    expect(container.firstChild).toBeNull()
  })

  it('marks the last item with aria-current=page', () => {
    renderBreadcrumbs({
      items: [
        { label: 'Tasks', to: '/tasks' },
        { label: 'Detail' },
      ],
    })
    expect(screen.getByText('Detail')).toHaveAttribute('aria-current', 'page')
  })

  it('renders links for ancestors with `to`', () => {
    renderBreadcrumbs({
      items: [
        { label: 'Tasks', to: '/tasks' },
        { label: 'T-1' },
      ],
    })
    const link = screen.getByRole('link', { name: 'Tasks' })
    expect(link).toHaveAttribute('href', '/tasks')
  })

  it('wraps in a nav with aria-label=Breadcrumb', () => {
    renderBreadcrumbs({
      items: [{ label: 'Home' }],
    })
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument()
  })

  it('collapses middle items when exceeding maxItems', () => {
    renderBreadcrumbs({
      items: [
        { label: 'A', to: '/a' },
        { label: 'B', to: '/b' },
        { label: 'C', to: '/c' },
        { label: 'D', to: '/d' },
        { label: 'E' },
      ],
      maxItems: 4,
    })
    // First + last should render, middle collapsed
    expect(screen.getByText('A')).toBeInTheDocument()
    expect(screen.getByText('E')).toBeInTheDocument()
    expect(screen.queryByText('B')).not.toBeInTheDocument()
  })

  it('renders all items when under maxItems threshold', () => {
    renderBreadcrumbs({
      items: [
        { label: 'A', to: '/a' },
        { label: 'B', to: '/b' },
        { label: 'C' },
      ],
      maxItems: 4,
    })
    expect(screen.getByText('A')).toBeInTheDocument()
    expect(screen.getByText('B')).toBeInTheDocument()
    expect(screen.getByText('C')).toBeInTheDocument()
  })

  it('uses <ol> list semantics', () => {
    const { container } = renderBreadcrumbs({
      items: [{ label: 'Home' }],
    })
    expect(container.querySelector('ol')).toBeInTheDocument()
  })
})
