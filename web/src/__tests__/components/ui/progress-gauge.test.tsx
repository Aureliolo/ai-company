import { render, screen } from '@testing-library/react'
import { ProgressGauge } from '@/components/ui/progress-gauge'

describe('ProgressGauge', () => {
  it('renders the percentage value', () => {
    render(<ProgressGauge value={75} />)

    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('renders the label when provided', () => {
    render(<ProgressGauge value={50} label="Budget" />)

    expect(screen.getByText('Budget')).toBeInTheDocument()
  })

  it('clamps value to 0 minimum', () => {
    render(<ProgressGauge value={-10} />)

    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('clamps value to max', () => {
    render(<ProgressGauge value={150} max={100} />)

    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('computes percentage from custom max', () => {
    render(<ProgressGauge value={50} max={200} />)

    expect(screen.getByText('25%')).toBeInTheDocument()
  })

  it('renders SVG with arc', () => {
    const { container } = render(<ProgressGauge value={60} />)

    expect(container.querySelector('svg')).toBeInTheDocument()
    expect(container.querySelectorAll('path').length).toBeGreaterThanOrEqual(1)
  })

  it('has accessible role and label', () => {
    render(<ProgressGauge value={75} label="CPU" />)

    const gauge = screen.getByRole('meter')
    expect(gauge).toHaveAttribute('aria-valuenow', '75')
    expect(gauge).toHaveAttribute('aria-valuemin', '0')
    expect(gauge).toHaveAttribute('aria-valuemax', '100')
  })

  it('applies custom className', () => {
    const { container } = render(<ProgressGauge value={50} className="my-class" />)

    expect(container.firstChild).toHaveClass('my-class')
  })
})
