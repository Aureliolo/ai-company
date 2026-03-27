import { render, screen } from '@testing-library/react'
import { BudgetSkeleton } from '@/pages/budget/BudgetSkeleton'

describe('BudgetSkeleton', () => {
  it('renders a loading status with correct aria-label', () => {
    render(<BudgetSkeleton />)
    const status = screen.getByRole('status')
    expect(status).toBeInTheDocument()
    expect(status).toHaveAttribute('aria-label', 'Loading budget')
  })

  it('renders metrics row with 4 skeleton metrics', () => {
    render(<BudgetSkeleton />)
    const metricsRow = screen.getByTestId('skeleton-metrics-row')
    expect(metricsRow.children).toHaveLength(4)
  })

  it('renders gauge and chart row with 2 skeleton cards', () => {
    render(<BudgetSkeleton />)
    const gaugeChartRow = screen.getByTestId('skeleton-gauge-chart-row')
    expect(gaugeChartRow.children).toHaveLength(2)
  })

  it('renders breakdown row with 2 skeleton cards', () => {
    render(<BudgetSkeleton />)
    const breakdownRow = screen.getByTestId('skeleton-breakdown-row')
    expect(breakdownRow.children).toHaveLength(2)
  })

  it('has aria-live polite for screen readers', () => {
    render(<BudgetSkeleton />)
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
  })
})
