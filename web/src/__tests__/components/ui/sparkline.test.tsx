import { render } from '@testing-library/react'
import { Sparkline } from '@/components/ui/sparkline'

describe('Sparkline', () => {
  it('renders an SVG with correct default dimensions', () => {
    const { container } = render(<Sparkline data={[1, 2, 3]} />)
    const svg = container.querySelector('svg')

    expect(svg).toBeInTheDocument()
    expect(svg).toHaveAttribute('width', '64')
    expect(svg).toHaveAttribute('height', '24')
  })

  it('renders with custom dimensions', () => {
    const { container } = render(<Sparkline data={[1, 2, 3]} width={60} height={28} />)
    const svg = container.querySelector('svg')

    expect(svg).toHaveAttribute('width', '60')
    expect(svg).toHaveAttribute('height', '28')
  })

  it('renders nothing for empty data', () => {
    const { container } = render(<Sparkline data={[]} />)

    expect(container.querySelector('svg')).not.toBeInTheDocument()
  })

  it('renders nothing for single data point', () => {
    const { container } = render(<Sparkline data={[5]} />)

    expect(container.querySelector('svg')).not.toBeInTheDocument()
  })

  it('renders a polyline element', () => {
    const { container } = render(<Sparkline data={[1, 3, 2, 4]} />)
    const polyline = container.querySelector('polyline')

    expect(polyline).toBeInTheDocument()
  })

  it('renders an end dot circle', () => {
    const { container } = render(<Sparkline data={[1, 3, 2, 4]} />)
    const circles = container.querySelectorAll('circle')

    expect(circles.length).toBeGreaterThanOrEqual(1)
  })

  it('renders a gradient definition', () => {
    const { container } = render(<Sparkline data={[1, 2, 3]} />)
    const defs = container.querySelector('defs')

    expect(defs).toBeInTheDocument()
  })

  it('applies custom className', () => {
    const { container } = render(<Sparkline data={[1, 2, 3]} className="my-class" />)
    const svg = container.querySelector('svg')

    expect(svg).toHaveClass('my-class')
  })

  it('does not inject animation style when animated is false', () => {
    const { container } = render(<Sparkline data={[1, 2, 3]} animated={false} />)

    expect(container.querySelector('style')).not.toBeInTheDocument()
  })

  it('renders correctly for flat data (all identical values)', () => {
    const { container } = render(<Sparkline data={[5, 5, 5]} />)
    const svg = container.querySelector('svg')

    expect(svg).toBeInTheDocument()
    expect(container.querySelector('polyline')).toBeInTheDocument()
  })
})
