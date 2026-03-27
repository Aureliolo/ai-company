import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DepartmentStatsBar } from '@/pages/org/DepartmentStatsBar'
import { formatCurrency } from '@/utils/format'

describe('DepartmentStatsBar', () => {
  it('renders all stat values and labels', () => {
    render(<DepartmentStatsBar agentCount={5} activeCount={3} taskCount={8} costUsd={null} />)
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('Tasks')).toBeInTheDocument()
  })

  it('renders cost with default USD currency', () => {
    render(<DepartmentStatsBar agentCount={5} activeCount={3} taskCount={8} costUsd={45.8} />)
    expect(screen.getByText(formatCurrency(45.8, 'USD'))).toBeInTheDocument()
    expect(screen.getByText('Cost')).toBeInTheDocument()
  })

  it('forwards explicit currency to formatCurrency', () => {
    render(<DepartmentStatsBar agentCount={1} activeCount={0} taskCount={0} costUsd={100} currency="EUR" />)
    expect(screen.getByText(formatCurrency(100, 'EUR'))).toBeInTheDocument()
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
