import { render, screen } from '@testing-library/react'
import { ApprovalsSkeleton } from '@/pages/approvals/ApprovalsSkeleton'

describe('ApprovalsSkeleton', () => {
  it('renders with role="status" and aria-label="Loading approvals"', () => {
    render(<ApprovalsSkeleton />)
    const skeleton = screen.getByRole('status')
    expect(skeleton).toHaveAttribute('aria-label', 'Loading approvals')
  })

  it('contains skeleton elements for filter bar', () => {
    const { container } = render(<ApprovalsSkeleton />)
    // Filter bar section has 4 skeleton elements (3 selects + 1 search)
    const filterRow = container.querySelector('.flex.items-center.gap-3')
    expect(filterRow).toBeInTheDocument()
    const filterSkeletons = filterRow!.querySelectorAll('.h-8')
    expect(filterSkeletons.length).toBe(4)
  })

  it('contains skeleton elements for metric cards', () => {
    const { container } = render(<ApprovalsSkeleton />)
    // 4 SkeletonMetric components
    const metricLabels = container.querySelectorAll('[data-testid="skeleton-label"]')
    expect(metricLabels.length).toBe(4)
    const metricValues = container.querySelectorAll('[data-testid="skeleton-value"]')
    expect(metricValues.length).toBe(4)
  })

  it('contains skeleton elements for risk group sections', () => {
    const { container } = render(<ApprovalsSkeleton />)
    // 3 SkeletonCard components with headers
    const headers = container.querySelectorAll('[data-skeleton-header]')
    expect(headers.length).toBe(3)
  })
})
