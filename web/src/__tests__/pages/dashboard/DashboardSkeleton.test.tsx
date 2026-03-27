import { render, screen } from '@testing-library/react'
import { DashboardSkeleton } from '@/pages/dashboard/DashboardSkeleton'

describe('DashboardSkeleton', () => {
  it('renders a loading status', () => {
    render(<DashboardSkeleton />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders metrics row with 4 skeleton cards', () => {
    render(<DashboardSkeleton />)
    const metricsRow = screen.getByTestId('skeleton-metrics-row')
    // Each SkeletonMetric renders a div with bg-card class
    expect(metricsRow.children).toHaveLength(4)
  })

  it('renders sections row with 2 skeleton cards', () => {
    render(<DashboardSkeleton />)
    const sectionsRow = screen.getByTestId('skeleton-sections-row')
    expect(sectionsRow.children).toHaveLength(2)
  })

  it('renders chart skeleton', () => {
    render(<DashboardSkeleton />)
    expect(screen.getByTestId('skeleton-chart')).toBeInTheDocument()
  })
})
