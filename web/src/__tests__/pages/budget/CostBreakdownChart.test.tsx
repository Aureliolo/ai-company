import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CostBreakdownChart } from '@/pages/budget/CostBreakdownChart'
import type { BreakdownSlice } from '@/utils/budget'

const SAMPLE_BREAKDOWN: BreakdownSlice[] = [
  { key: 'agent-1', label: 'Alice', cost: 120, percent: 40, color: 'var(--so-accent)' },
  { key: 'agent-2', label: 'Bob', cost: 90, percent: 30, color: 'var(--so-success)' },
  { key: 'agent-3', label: 'Carol', cost: 90, percent: 30, color: 'var(--so-warning)' },
]

const MANY_SLICES: BreakdownSlice[] = [
  { key: 'a1', label: 'Agent 1', cost: 100, percent: 20, color: 'var(--so-accent)' },
  { key: 'a2', label: 'Agent 2', cost: 80, percent: 16, color: 'var(--so-success)' },
  { key: 'a3', label: 'Agent 3', cost: 70, percent: 14, color: 'var(--so-warning)' },
  { key: 'a4', label: 'Agent 4', cost: 60, percent: 12, color: 'var(--so-danger)' },
  { key: 'a5', label: 'Agent 5', cost: 50, percent: 10, color: 'var(--so-text-secondary)' },
  { key: 'a6', label: 'Agent 6', cost: 40, percent: 8, color: 'var(--so-text-muted)' },
  { key: 'a7', label: 'Agent 7', cost: 30, percent: 6, color: 'var(--so-accent)' },
  { key: 'a8', label: 'Agent 8', cost: 20, percent: 4, color: 'var(--so-success)' },
  { key: 'a9', label: 'Agent 9', cost: 15, percent: 3, color: 'var(--so-warning)' },
  { key: 'a10', label: 'Agent 10', cost: 10, percent: 2, color: 'var(--so-danger)' },
]

describe('CostBreakdownChart', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const defaultProps = {
    breakdown: SAMPLE_BREAKDOWN,
    dimension: 'agent' as const,
    onDimensionChange: vi.fn(),
  }

  it('renders section title', () => {
    render(<CostBreakdownChart {...defaultProps} />)
    expect(screen.getByText('Cost Breakdown')).toBeInTheDocument()
  })

  it('shows empty state when no data', () => {
    render(
      <CostBreakdownChart
        {...defaultProps}
        breakdown={[]}
      />,
    )
    expect(screen.getByText('No cost data')).toBeInTheDocument()
  })

  it('renders donut chart when data is provided', () => {
    render(<CostBreakdownChart {...defaultProps} />)
    expect(screen.getByTestId('cost-breakdown-chart')).toBeInTheDocument()
  })

  it('renders toggle buttons for all dimensions', () => {
    render(<CostBreakdownChart {...defaultProps} />)
    expect(screen.getByRole('radio', { name: 'Agent' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Dept' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Provider' })).toBeInTheDocument()
  })

  it('marks active dimension with aria-checked', () => {
    render(<CostBreakdownChart {...defaultProps} dimension="provider" />)
    expect(screen.getByRole('radio', { name: 'Provider' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Agent' })).toHaveAttribute('aria-checked', 'false')
  })

  it('fires onDimensionChange when toggle is clicked', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <CostBreakdownChart
        {...defaultProps}
        onDimensionChange={onChange}
      />,
    )
    await user.click(screen.getByRole('radio', { name: 'Provider' }))
    expect(onChange).toHaveBeenCalledWith('provider')
  })

  it('disables Dept button when deptDisabled is true', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <CostBreakdownChart
        {...defaultProps}
        onDimensionChange={onChange}
        deptDisabled
      />,
    )
    const deptBtn = screen.getByRole('radio', { name: 'Dept' })
    expect(deptBtn).toBeDisabled()
    await user.click(deptBtn)
    expect(onChange).not.toHaveBeenCalled()
  })

  it('renders legend with slice labels and costs', () => {
    render(<CostBreakdownChart {...defaultProps} />)
    const legend = screen.getByTestId('cost-breakdown-legend')
    expect(legend).toBeInTheDocument()
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('Bob')).toBeInTheDocument()
    expect(screen.getByText('Carol')).toBeInTheDocument()
  })

  it('collapses excess slices into "Other" in the legend', () => {
    render(
      <CostBreakdownChart
        {...defaultProps}
        breakdown={MANY_SLICES}
      />,
    )
    // First 6 should appear by name
    expect(screen.getByText('Agent 1')).toBeInTheDocument()
    expect(screen.getByText('Agent 6')).toBeInTheDocument()
    // Agents 7-10 should be collapsed
    expect(screen.queryByText('Agent 7')).not.toBeInTheDocument()
    expect(screen.getByText('Other')).toBeInTheDocument()
  })

  it('renders with custom currency', () => {
    render(
      <CostBreakdownChart
        {...defaultProps}
        currency="USD"
      />,
    )
    // Legend should show USD-formatted costs
    expect(screen.getByText(/\$120\.00/)).toBeInTheDocument()
  })

  it('renders the radiogroup with correct label', () => {
    render(<CostBreakdownChart {...defaultProps} />)
    expect(screen.getByRole('radiogroup', { name: 'Breakdown dimension' })).toBeInTheDocument()
  })
})
