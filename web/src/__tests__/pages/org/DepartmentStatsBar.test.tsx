import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DepartmentStatsBar } from '@/pages/org/DepartmentStatsBar'
import { formatCurrency } from '@/utils/format'

describe('DepartmentStatsBar', () => {
  it.each([
    [5, 'Agents'],
    [3, 'Active'],
    [8, 'Tasks'],
  ])('renders %s with label %s', (value, label) => {
    render(<DepartmentStatsBar agentCount={5} activeCount={3} taskCount={8} costUsd={null} />)
    expect(screen.getByText(String(value))).toBeInTheDocument()
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('renders cost when provided', () => {
    render(<DepartmentStatsBar agentCount={5} activeCount={3} taskCount={8} costUsd={45.8} />)
    expect(screen.getByText(formatCurrency(45.8, 'USD'))).toBeInTheDocument()
    expect(screen.getByText('Cost')).toBeInTheDocument()
  })

  it('does not render cost when null', () => {
    render(<DepartmentStatsBar agentCount={5} activeCount={3} taskCount={8} costUsd={null} />)
    expect(screen.queryByText('Cost')).not.toBeInTheDocument()
  })

  it('has data-testid', () => {
    render(<DepartmentStatsBar agentCount={1} activeCount={0} taskCount={0} costUsd={null} />)
    expect(screen.getByTestId('dept-stats-bar')).toBeInTheDocument()
  })
})
