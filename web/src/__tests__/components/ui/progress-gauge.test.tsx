import { render, screen } from '@testing-library/react'
import * as fc from 'fast-check'
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

  it('renders small size variant with different dimensions', () => {
    const { container } = render(<ProgressGauge value={50} size="sm" />)
    const svg = container.querySelector('svg')

    expect(svg).toBeInTheDocument()
    // sm radius=32, stroke=6 -> svgWidth=(32+6)*2=76, md radius=48 -> svgWidth=(48+6)*2=108
    expect(svg).toHaveAttribute('width', '76')
  })

  it('handles max=0 without NaN', () => {
    render(<ProgressGauge value={50} max={0} />)

    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('always clamps percentage between 0 and 100 (property)', () => {
    fc.assert(
      fc.property(
        fc.float({ min: -1000, max: 1000, noNaN: true }),
        fc.float({ min: 1, max: 1000, noNaN: true }),
        (value, max) => {
          const { unmount } = render(<ProgressGauge value={value} max={max} />)
          const text = screen.getByText(/%$/)
          const percentage = parseInt(text.textContent ?? '0')
          expect(percentage).toBeGreaterThanOrEqual(0)
          expect(percentage).toBeLessThanOrEqual(100)
          unmount()
        },
      ),
    )
  })

  it('treats NaN value as 0%', () => {
    render(<ProgressGauge value={NaN} />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('treats Infinity as non-finite and defaults to 0%', () => {
    render(<ProgressGauge value={Infinity} />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('treats -Infinity as non-finite and defaults to 0%', () => {
    render(<ProgressGauge value={-Infinity} />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('treats NaN max as 1 (no division by zero)', () => {
    render(<ProgressGauge value={50} max={NaN} />)
    // safeMax becomes 1, clampedValue = min(50, 1) = 1, percentage = 100%
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('defaults to circular variant (SVG present)', () => {
    const { container } = render(<ProgressGauge value={50} />)
    expect(container.querySelector('svg')).toBeInTheDocument()
  })
})

describe('ProgressGauge linear variant', () => {
  it('renders the percentage value', () => {
    render(<ProgressGauge value={75} variant="linear" />)
    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('renders the label when provided', () => {
    render(<ProgressGauge value={50} variant="linear" label="Budget" />)
    expect(screen.getByText('Budget')).toBeInTheDocument()
  })

  it('clamps value to 0 minimum', () => {
    render(<ProgressGauge value={-10} variant="linear" />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('clamps value to max', () => {
    render(<ProgressGauge value={150} max={100} variant="linear" />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('computes percentage from custom max', () => {
    render(<ProgressGauge value={50} max={200} variant="linear" />)
    expect(screen.getByText('25%')).toBeInTheDocument()
  })

  it('does not render SVG', () => {
    const { container } = render(<ProgressGauge value={60} variant="linear" />)
    expect(container.querySelector('svg')).not.toBeInTheDocument()
  })

  it('renders a bar track and fill', () => {
    const { container } = render(<ProgressGauge value={60} variant="linear" />)
    const track = container.querySelector('.bg-border')
    expect(track).toBeInTheDocument()
    expect(track?.firstElementChild).toBeInTheDocument()
  })

  it('has accessible role and aria attributes', () => {
    render(<ProgressGauge value={75} variant="linear" label="CPU" />)
    const gauge = screen.getByRole('meter')
    expect(gauge).toHaveAttribute('aria-valuenow', '75')
    expect(gauge).toHaveAttribute('aria-valuemin', '0')
    expect(gauge).toHaveAttribute('aria-valuemax', '100')
  })

  it('applies custom className', () => {
    const { container } = render(
      <ProgressGauge value={50} variant="linear" className="my-class" />,
    )
    expect(container.firstChild).toHaveClass('my-class')
  })

  it('applies bg-danger for low values', () => {
    const { container } = render(<ProgressGauge value={10} variant="linear" />)
    const track = container.querySelector('.bg-border')
    expect(track?.firstElementChild).toHaveClass('bg-danger')
  })

  it('applies bg-warning for moderate values', () => {
    const { container } = render(<ProgressGauge value={35} variant="linear" />)
    const track = container.querySelector('.bg-border')
    expect(track?.firstElementChild).toHaveClass('bg-warning')
  })

  it('applies bg-accent for mid-range values', () => {
    const { container } = render(<ProgressGauge value={60} variant="linear" />)
    const track = container.querySelector('.bg-border')
    expect(track?.firstElementChild).toHaveClass('bg-accent')
  })

  it('applies bg-success for high values', () => {
    const { container } = render(<ProgressGauge value={90} variant="linear" />)
    const track = container.querySelector('.bg-border')
    expect(track?.firstElementChild).toHaveClass('bg-success')
  })

  it('sets fill width to percentage', () => {
    const { container } = render(<ProgressGauge value={75} variant="linear" />)
    const track = container.querySelector('.bg-border')
    expect(track?.firstElementChild).toHaveStyle({ width: '75%' })
  })

  it('handles NaN value as 0%', () => {
    render(<ProgressGauge value={NaN} variant="linear" />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('handles Infinity as 0%', () => {
    render(<ProgressGauge value={Infinity} variant="linear" />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('always clamps percentage between 0 and 100 (property)', () => {
    fc.assert(
      fc.property(
        fc.float({ min: -1000, max: 1000, noNaN: true }),
        fc.float({ min: 1, max: 1000, noNaN: true }),
        (value, max) => {
          const { unmount } = render(
            <ProgressGauge value={value} max={max} variant="linear" />,
          )
          const text = screen.getByText(/%$/)
          const percentage = parseInt(text.textContent ?? '0')
          expect(percentage).toBeGreaterThanOrEqual(0)
          expect(percentage).toBeLessThanOrEqual(100)
          unmount()
        },
      ),
    )
  })
})
