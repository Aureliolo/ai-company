import { render, screen } from '@testing-library/react'
import { OrgHealthSection } from '@/pages/dashboard/OrgHealthSection'
import type { DepartmentHealth } from '@/api/types'

function makeDepts(count: number): DepartmentHealth[] {
  const names = ['engineering', 'design', 'product', 'operations', 'security'] as const
  return Array.from({ length: count }, (_, i) => {
    const name = names[i % names.length]!
    return {
      name,
      display_name: name.charAt(0).toUpperCase() + name.slice(1),
      health_percent: 60 + i * 10,
      agent_count: 2 + i,
      task_count: 5 + i,
      cost_usd: null,
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

  it('renders department cost when cost_usd is non-null (EUR default)', () => {
    const depts = makeDepts(1).map((d) => ({ ...d, cost_usd: 24.5 }))
    render(<OrgHealthSection departments={depts} overallHealth={80} />)
    expect(screen.getByText(/24\.50/)).toBeInTheDocument()
  })

  it('renders department cost in specified currency', () => {
    const depts = makeDepts(1).map((d) => ({ ...d, cost_usd: 100 }))
    render(<OrgHealthSection departments={depts} overallHealth={80} currency="JPY" />)
    expect(screen.getByText(/100/)).toBeInTheDocument()
  })
})
