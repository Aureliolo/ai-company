import { render } from '@testing-library/react'
import {
  Skeleton,
  SkeletonCard,
  SkeletonMetric,
  SkeletonTable,
  SkeletonText,
} from '@/components/ui/skeleton'

describe('Skeleton', () => {
  it('renders a div', () => {
    const { container } = render(<Skeleton />)
    expect(container.firstChild).toBeInTheDocument()
  })

  it('applies shimmer class by default', () => {
    const { container } = render(<Skeleton />)
    expect(container.firstChild).toHaveClass('so-shimmer')
  })

  it('omits shimmer class when shimmer=false', () => {
    const { container } = render(<Skeleton shimmer={false} />)
    expect(container.firstChild).not.toHaveClass('so-shimmer')
  })

  it('applies custom className', () => {
    const { container } = render(<Skeleton className="h-8 w-32" />)
    expect(container.firstChild).toHaveClass('h-8', 'w-32')
  })
})

describe('SkeletonText', () => {
  it('renders 3 lines by default', () => {
    const { container } = render(<SkeletonText />)
    const lines = container.querySelectorAll('.rounded')
    expect(lines).toHaveLength(3)
  })

  it('renders custom number of lines', () => {
    const { container } = render(<SkeletonText lines={5} />)
    const lines = container.querySelectorAll('.rounded')
    expect(lines).toHaveLength(5)
  })

  it('last line has reduced width', () => {
    const { container } = render(<SkeletonText />)
    const lines = container.querySelectorAll('.rounded')
    const lastLine = lines[lines.length - 1]
    expect(lastLine).toHaveStyle({ width: '60%' })
  })
})

describe('SkeletonCard', () => {
  it('renders header when header=true', () => {
    const { container } = render(<SkeletonCard header />)
    // Header is the first child of the card
    const children = container.querySelectorAll('.rounded')
    expect(children.length).toBeGreaterThan(0)
  })

  it('renders body lines', () => {
    const { container } = render(<SkeletonCard lines={4} />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper).toBeInTheDocument()
  })
})

describe('SkeletonMetric', () => {
  it('renders metric skeleton layout', () => {
    const { container } = render(<SkeletonMetric />)
    expect(container.firstChild).toBeInTheDocument()
    // Should have label, value, and optionally progress bar skeletons
    const skeletons = container.querySelectorAll('.rounded')
    expect(skeletons.length).toBeGreaterThanOrEqual(2)
  })
})

describe('SkeletonTable', () => {
  it('renders default 5 rows and 4 columns', () => {
    const { container } = render(<SkeletonTable />)
    const rows = container.querySelectorAll('[data-skeleton-row]')
    expect(rows).toHaveLength(5)
    const firstRowCells = rows[0]?.querySelectorAll('.rounded')
    expect(firstRowCells).toHaveLength(4)
  })

  it('renders custom rows and columns', () => {
    const { container } = render(<SkeletonTable rows={3} columns={6} />)
    const rows = container.querySelectorAll('[data-skeleton-row]')
    expect(rows).toHaveLength(3)
    const firstRowCells = rows[0]?.querySelectorAll('.rounded')
    expect(firstRowCells).toHaveLength(6)
  })
})
