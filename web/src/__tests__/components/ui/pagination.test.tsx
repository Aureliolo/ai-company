import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import fc from 'fast-check'
import { Pagination } from '@/components/ui/pagination'

describe('Pagination', () => {
  it('renders range and total', () => {
    render(
      <Pagination page={2} pageSize={20} total={100} onPageChange={() => {}} />,
    )
    expect(screen.getByText(/21-40 of 100/)).toBeInTheDocument()
  })

  it('disables First/Previous on first page', () => {
    render(
      <Pagination page={1} pageSize={20} total={100} onPageChange={() => {}} />,
    )
    expect(screen.getByRole('button', { name: 'First page' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
  })

  it('disables Next/Last on last page', () => {
    render(
      <Pagination page={5} pageSize={20} total={100} onPageChange={() => {}} />,
    )
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Last page' })).toBeDisabled()
  })

  it('calls onPageChange when Next clicked', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()
    render(
      <Pagination page={1} pageSize={20} total={100} onPageChange={onPageChange} />,
    )
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('calls onPageChange(totalPages) when Last clicked', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()
    render(
      <Pagination page={1} pageSize={20} total={100} onPageChange={onPageChange} />,
    )
    await user.click(screen.getByRole('button', { name: 'Last page' }))
    expect(onPageChange).toHaveBeenCalledWith(5)
  })

  it('keyboard: ArrowRight advances page', () => {
    const onPageChange = vi.fn()
    render(
      <Pagination page={2} pageSize={20} total={100} onPageChange={onPageChange} />,
    )
    const nav = screen.getByRole('navigation', { name: 'Pagination' })
    act(() => { fireEvent.keyDown(nav, { key: 'ArrowRight' }) })
    expect(onPageChange).toHaveBeenCalledWith(3)
  })

  it('keyboard: Home jumps to first page', () => {
    const onPageChange = vi.fn()
    render(
      <Pagination page={4} pageSize={20} total={100} onPageChange={onPageChange} />,
    )
    const nav = screen.getByRole('navigation', { name: 'Pagination' })
    act(() => { fireEvent.keyDown(nav, { key: 'Home' }) })
    expect(onPageChange).toHaveBeenCalledWith(1)
  })

  it('keyboard: End jumps to last page', () => {
    const onPageChange = vi.fn()
    render(
      <Pagination page={2} pageSize={20} total={100} onPageChange={onPageChange} />,
    )
    const nav = screen.getByRole('navigation', { name: 'Pagination' })
    act(() => { fireEvent.keyDown(nav, { key: 'End' }) })
    expect(onPageChange).toHaveBeenCalledWith(5)
  })

  it('renders No items when total is 0', () => {
    render(
      <Pagination page={1} pageSize={20} total={0} onPageChange={() => {}} />,
    )
    expect(screen.getByText('No items')).toBeInTheDocument()
  })

  it('shows page only when total is undefined (cursor mode)', () => {
    render(
      <Pagination page={3} pageSize={20} total={undefined} onPageChange={() => {}} />,
    )
    expect(screen.getByText('Page 3')).toBeInTheDocument()
  })

  it('page size selector fires onPageSizeChange', async () => {
    const user = userEvent.setup()
    const onPageSizeChange = vi.fn()
    render(
      <Pagination
        page={1}
        pageSize={20}
        total={100}
        onPageChange={() => {}}
        onPageSizeChange={onPageSizeChange}
      />,
    )
    await user.selectOptions(screen.getByLabelText('Items per page'), '50')
    expect(onPageSizeChange).toHaveBeenCalledWith(50)
  })

  it('hides page size selector when hidePageSize is true', () => {
    render(
      <Pagination
        page={1}
        pageSize={20}
        total={100}
        onPageChange={() => {}}
        onPageSizeChange={() => {}}
        hidePageSize
      />,
    )
    expect(screen.queryByLabelText('Items per page')).not.toBeInTheDocument()
  })

  it('property: First/Previous always disabled on the first page; Next/Last enabled as long as more pages remain', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 200 }),
        fc.integer({ min: 1, max: 500 }),
        (total, pageSize) => {
          const { unmount } = render(
            <Pagination page={1} pageSize={pageSize} total={total} onPageChange={() => {}} />,
          )
          expect(screen.getByRole('button', { name: 'First page' })).toBeDisabled()
          expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
          const hasMore = total > pageSize
          const nextBtn = screen.getByRole('button', { name: 'Next page' })
          const lastBtn = screen.getByRole('button', { name: 'Last page' })
          if (hasMore) {
            expect(nextBtn).not.toBeDisabled()
            expect(lastBtn).not.toBeDisabled()
          } else {
            expect(nextBtn).toBeDisabled()
            expect(lastBtn).toBeDisabled()
          }
          unmount()
        },
      ),
    )
  })
})
