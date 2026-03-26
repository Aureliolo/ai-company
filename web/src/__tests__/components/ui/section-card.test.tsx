import { render, screen } from '@testing-library/react'
import { Settings } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'

describe('SectionCard', () => {
  it('renders title text', () => {
    render(<SectionCard title="Overview">Content</SectionCard>)

    expect(screen.getByText('Overview')).toBeInTheDocument()
  })

  it('renders children content', () => {
    render(<SectionCard title="Overview">Hello world</SectionCard>)

    expect(screen.getByText('Hello world')).toBeInTheDocument()
  })

  it('renders icon when provided', () => {
    const { container } = render(
      <SectionCard title="Settings" icon={Settings}>Content</SectionCard>,
    )

    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('does not render icon when not provided', () => {
    const { container } = render(
      <SectionCard title="Overview">Content</SectionCard>,
    )

    expect(container.querySelector('svg')).not.toBeInTheDocument()
  })

  it('renders action slot when provided', () => {
    render(
      <SectionCard title="Overview" action={<button>Edit</button>}>
        Content
      </SectionCard>,
    )

    expect(screen.getByText('Edit')).toBeInTheDocument()
  })

  it('applies custom className', () => {
    const { container } = render(
      <SectionCard title="Overview" className="my-class">Content</SectionCard>,
    )

    expect(container.firstChild).toHaveClass('my-class')
  })
})
