import { render, screen } from '@testing-library/react'
import fc from 'fast-check'
import { ProgressIndicator } from '@/components/ui/progress-indicator'

describe('ProgressIndicator', () => {
  it('determinate: renders percent + aria-valuenow', () => {
    render(<ProgressIndicator variant="determinate" value={42} label="Training" />)
    const bar = screen.getByRole('progressbar', { name: 'Training' })
    expect(bar).toHaveAttribute('aria-valuenow', '42')
    expect(bar).toHaveAttribute('aria-valuemin', '0')
    expect(bar).toHaveAttribute('aria-valuemax', '100')
    expect(screen.getByText('42%')).toBeInTheDocument()
  })

  it('determinate: clamps value to [0, 100]', () => {
    render(<ProgressIndicator variant="determinate" value={-5} label="A" />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')

    const { rerender } = render(<ProgressIndicator variant="determinate" value={150} label="B" />)
    rerender(<ProgressIndicator variant="determinate" value={150} label="B" />)
    // Two progressbars rendered; just check the second one
    const bars = screen.getAllByRole('progressbar')
    expect(bars[bars.length - 1]).toHaveAttribute('aria-valuenow', '100')
  })

  it('indeterminate: has aria-busy=true', () => {
    render(<ProgressIndicator variant="indeterminate" label="Loading" />)
    const bar = screen.getByRole('progressbar', { name: 'Loading' })
    expect(bar).toHaveAttribute('aria-busy', 'true')
  })

  it('stages: renders all stages with correct labels', () => {
    render(
      <ProgressIndicator
        variant="stages"
        stages={[
          { id: '1', label: 'Step One', status: 'done' },
          { id: '2', label: 'Step Two', status: 'running' },
          { id: '3', label: 'Step Three', status: 'pending' },
        ]}
      />,
    )
    expect(screen.getByText('Step One')).toBeInTheDocument()
    expect(screen.getByText('Step Two')).toBeInTheDocument()
    expect(screen.getByText('Step Three')).toBeInTheDocument()
  })

  it('stages: exposes status in aria-label', () => {
    render(
      <ProgressIndicator
        variant="stages"
        stages={[{ id: '1', label: 'X', status: 'failed' }]}
      />,
    )
    expect(screen.getByLabelText('X: failed')).toBeInTheDocument()
  })

  it('stages: renders description', () => {
    render(
      <ProgressIndicator
        variant="stages"
        stages={[{ id: '1', label: 'S', status: 'running', description: 'Epoch 2' }]}
      />,
    )
    expect(screen.getByText('Epoch 2')).toBeInTheDocument()
  })

  it('renders label and description', () => {
    render(
      <ProgressIndicator
        variant="determinate"
        value={50}
        label="Upload"
        description="2.5 MB / 5 MB"
      />,
    )
    expect(screen.getByText('Upload')).toBeInTheDocument()
    expect(screen.getByText('2.5 MB / 5 MB')).toBeInTheDocument()
  })

  it('indeterminate: renders description even when label is absent', () => {
    render(<ProgressIndicator variant="indeterminate" description="Warming up..." />)
    expect(screen.getByText('Warming up...')).toBeInTheDocument()
  })

  it('property: determinate clamp invariant holds for any finite value', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: -10_000, max: 10_000 }),
        (value) => {
          const { unmount } = render(
            <ProgressIndicator variant="determinate" value={value} label="Clamp" />,
          )
          const bar = screen.getByRole('progressbar', { name: 'Clamp' })
          const expected = String(Math.min(100, Math.max(0, Math.round(value))))
          expect(bar).toHaveAttribute('aria-valuenow', expected)
          unmount()
        },
      ),
      { numRuns: 20 },
    )
  })
})
