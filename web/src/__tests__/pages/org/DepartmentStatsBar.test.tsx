import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DepartmentStatsBar } from '@/pages/org/DepartmentStatsBar'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import { formatCurrency } from '@/utils/format'

describe('DepartmentStatsBar', () => {
  it('renders agent and active stat values', () => {
    render(<DepartmentStatsBar agentCount={5} activeCount={3} cost7d={null} />)
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('renders cost with the default currency', () => {
    render(<DepartmentStatsBar agentCount={5} activeCount={3} cost7d={45.8} />)
    expect(
      screen.getByText(formatCurrency(45.8, DEFAULT_CURRENCY)),
    ).toBeInTheDocument()
    expect(screen.getByText('Cost (7d)')).toBeInTheDocument()
  })

  it('forwards explicit currency to formatCurrency', () => {
    render(<DepartmentStatsBar agentCount={1} activeCount={0} cost7d={100} currency="JPY" />)
    expect(screen.getByText(formatCurrency(100, 'JPY'))).toBeInTheDocument()
    expect(screen.getByText('Cost (7d)')).toBeInTheDocument()
  })

  it('does not render cost when null', () => {
    render(<DepartmentStatsBar agentCount={5} activeCount={3} cost7d={null} />)
    expect(screen.queryByText('Cost (7d)')).not.toBeInTheDocument()
  })

  it('has data-testid', () => {
    render(<DepartmentStatsBar agentCount={1} activeCount={0} cost7d={null} />)
    expect(screen.getByTestId('dept-stats-bar')).toBeInTheDocument()
  })
})
