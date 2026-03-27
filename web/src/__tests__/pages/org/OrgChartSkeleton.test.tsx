import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OrgChartSkeleton } from '@/pages/org/OrgChartSkeleton'

describe('OrgChartSkeleton', () => {
  it('renders with role="status"', () => {
    render(<OrgChartSkeleton />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('has aria-live="polite"', () => {
    render(<OrgChartSkeleton />)
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
  })

  it('has accessible label', () => {
    render(<OrgChartSkeleton />)
    expect(screen.getByLabelText('Loading org chart')).toBeInTheDocument()
  })
})
