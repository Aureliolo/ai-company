import { render, screen } from '@testing-library/react'
import { OrgHealthSection } from '@/pages/dashboard/OrgHealthSection'
import { formatCurrency } from '@/utils/format'
import type { DepartmentHealth } from '@/api/types/analytics'

function makeDepts(count: number): DepartmentHealth[] {
  const names = ['engineering', 'design', 'product', 'operations', 'security'] as const
  return Array.from({ length: count }, (_, i) => {
    const name = names[i % names.length]!
    return {
      department_name: name,
      agent_count: 2 + i,
      active_agent_count: 1 + i,
      currency: 'EUR',
      avg_performance_score: 7.0,
      department_cost_7d: 0,
      cost_trend: [],
      collaboration_score: 6.0,
      utilization_percent: 60 + i * 10,
    }
  })
}

describe('OrgHealthSection', () => {
  it('renders section title', () => {
    render(<OrgHealthSection departments={[]} overallHealth={null} />)
    expect(screen.getByText('Org Health')).toBeInTheDocument()
  })

  it('shows empty state when no departments', () => {
    render(<OrgHealthSection departments={[]} overallHealth={null} />)
    expect(screen.getByText('No departments configured')).toBeInTheDocument()
  })

  it('renders department health bars', () => {
    render(<OrgHealthSection departments={makeDepts(3)} overallHealth={70} />)
    expect(screen.getByText('Engineering')).toBeInTheDocument()
    expect(screen.getByText('Design')).toBeInTheDocument()
    expect(screen.getByText('Product')).toBeInTheDocument()
  })

  it('renders overall health gauge when provided', () => {
    render(<OrgHealthSection departments={makeDepts(1)} overallHealth={85} />)
    const meters = screen.getAllByRole('meter')
    expect(meters.length).toBeGreaterThanOrEqual(1)
  })

  it('renders department cost when department_cost_7d is positive', () => {
    const depts = makeDepts(1).map((d) => ({ ...d, department_cost_7d: 24.5 }))
    render(<OrgHealthSection departments={depts} overallHealth={80} />)
    expect(screen.getByText(formatCurrency(24.5, 'EUR'))).toBeInTheDocument()
  })

  it('renders department cost in its own currency', () => {
    const depts = makeDepts(1).map((d) => ({ ...d, department_cost_7d: 100, currency: 'JPY' }))
    render(<OrgHealthSection departments={depts} overallHealth={80} />)
    expect(screen.getByText(formatCurrency(100, 'JPY'))).toBeInTheDocument()
  })
})
