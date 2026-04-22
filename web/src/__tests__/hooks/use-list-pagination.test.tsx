import { act, renderHook } from '@testing-library/react'
import fc from 'fast-check'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { useListPagination } from '@/hooks/use-list-pagination'

function wrapper({ children, initialEntries = ['/'] }: { children: ReactNode; initialEntries?: string[] }) {
  return <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
}

function makeWrapper(initialEntries: string[] = ['/']) {
  return ({ children }: { children: ReactNode }) => wrapper({ children, initialEntries })
}

describe('useListPagination', () => {
  const ITEMS = Array.from({ length: 123 }, (_, i) => i)

  it('defaults to page 1 + pageSize 50', () => {
    const { result } = renderHook(() => useListPagination({ items: ITEMS }), {
      wrapper: makeWrapper(),
    })
    expect(result.current.page).toBe(1)
    expect(result.current.pageSize).toBe(50)
    expect(result.current.totalPages).toBe(3)
    expect(result.current.paginatedItems).toHaveLength(50)
    expect(result.current.paginatedItems[0]).toBe(0)
  })

  it('reads page + size from URL', () => {
    const { result } = renderHook(() => useListPagination({ items: ITEMS }), {
      wrapper: makeWrapper(['/?pPage=2&pSize=20']),
    })
    expect(result.current.page).toBe(2)
    expect(result.current.pageSize).toBe(20)
    expect(result.current.paginatedItems[0]).toBe(20)
    expect(result.current.paginatedItems).toHaveLength(20)
  })

  it('clamps page to totalPages', () => {
    const { result } = renderHook(() => useListPagination({ items: ITEMS, defaultPageSize: 50 }), {
      wrapper: makeWrapper(['/?pPage=99']),
    })
    // 123 items / 50 = 3 pages
    expect(result.current.page).toBe(3)
  })

  it('setPage updates URL', () => {
    const { result } = renderHook(() => useListPagination({ items: ITEMS }), {
      wrapper: makeWrapper(),
    })
    act(() => {
      result.current.setPage(2)
    })
    expect(result.current.page).toBe(2)
  })

  it('setPageSize resets to page 1', () => {
    const { result } = renderHook(() => useListPagination({ items: ITEMS }), {
      wrapper: makeWrapper(['/?pPage=2&pSize=20']),
    })
    act(() => {
      result.current.setPageSize(100)
    })
    expect(result.current.page).toBe(1)
    expect(result.current.pageSize).toBe(100)
  })

  it('setPageSize snaps invalid size to default', () => {
    const { result } = renderHook(() => useListPagination({ items: ITEMS, defaultPageSize: 50 }), {
      wrapper: makeWrapper(),
    })
    act(() => {
      result.current.setPageSize(77)
    })
    expect(result.current.pageSize).toBe(50)
  })

  it('resetPage sends user back to page 1', () => {
    const { result } = renderHook(() => useListPagination({ items: ITEMS }), {
      wrapper: makeWrapper(['/?pPage=2']),
    })
    act(() => {
      result.current.resetPage()
    })
    expect(result.current.page).toBe(1)
  })

  it('namespace allows multiple paginators on one page', () => {
    const { result: a } = renderHook(() => useListPagination({ items: ITEMS, namespace: 'a' }), {
      wrapper: makeWrapper(['/?aPage=2&bPage=3']),
    })
    const { result: b } = renderHook(() => useListPagination({ items: ITEMS, namespace: 'b' }), {
      wrapper: makeWrapper(['/?aPage=2&bPage=3']),
    })
    expect(a.current.page).toBe(2)
    expect(b.current.page).toBe(3)
  })

  it('empty list yields totalPages=1, paginatedItems=[]', () => {
    const { result } = renderHook(() => useListPagination({ items: [] as number[] }), {
      wrapper: makeWrapper(),
    })
    expect(result.current.totalPages).toBe(1)
    expect(result.current.paginatedItems).toHaveLength(0)
  })

  it('property: paginatedItems.length === min(pageSize, remaining) for any page/total', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 300 }),
        fc.constantFrom(20, 50, 100),
        fc.integer({ min: 1, max: 10 }),
        (total, pageSize, pageNumber) => {
          const items = Array.from({ length: total }, (_, i) => i)
          const { result } = renderHook(
            () => useListPagination({ items, defaultPageSize: pageSize }),
            { wrapper: makeWrapper([`/?pPage=${pageNumber}&pSize=${pageSize}`]) },
          )
          // page is clamped to [1, totalPages]
          const totalPages = total === 0 ? 1 : Math.max(1, Math.ceil(total / pageSize))
          expect(result.current.page).toBeGreaterThanOrEqual(1)
          expect(result.current.page).toBeLessThanOrEqual(totalPages)
          // slice length never exceeds pageSize
          expect(result.current.paginatedItems.length).toBeLessThanOrEqual(pageSize)
          // slice length never exceeds remaining items from the clamped start
          const start = (result.current.page - 1) * pageSize
          expect(result.current.paginatedItems.length).toBe(
            Math.max(0, Math.min(pageSize, total - start)),
          )
        },
      ),
    )
  })

  it('setPageSize(sameSize) is idempotent: current page stays put', () => {
    const { result } = renderHook(() => useListPagination({ items: ITEMS }), {
      wrapper: makeWrapper(['/?pPage=2&pSize=20']),
    })
    act(() => {
      result.current.setPageSize(20)
    })
    expect(result.current.page).toBe(2)
    expect(result.current.pageSize).toBe(20)
  })

  it('guards non-positive defaultPageSize', () => {
    const { result } = renderHook(
      () => useListPagination({ items: ITEMS, defaultPageSize: 0, pageSizeOptions: [20, 50, 100] }),
      { wrapper: makeWrapper() },
    )
    expect(result.current.pageSize).toBe(50)
    expect(result.current.totalPages).toBeGreaterThanOrEqual(1)
  })
})
