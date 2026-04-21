import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'

export interface UseListPaginationOptions<T> {
  /** The full unpaginated list. Slicing happens inside the hook. */
  items: readonly T[]
  /** URL query-param namespace; distinct namespaces let multiple paginators coexist on one page. Default 'p'. */
  namespace?: string
  /** Default page size when no ?pageSize param is present. Default 50. */
  defaultPageSize?: number
  /** Available page sizes; out-of-range values snap back to `defaultPageSize`. Default [20, 50, 100]. */
  pageSizeOptions?: readonly number[]
}

export interface UseListPaginationResult<T> {
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
  paginatedItems: readonly T[]
  setPage: (page: number) => void
  setPageSize: (size: number) => void
  /** Reset pagination to page 1 (keeps current pageSize). Call after filter/sort changes. */
  resetPage: () => void
}

const DEFAULT_SIZES = [20, 50, 100] as const

function parsePositiveInt(raw: string | null, fallback: number): number {
  if (!raw) return fallback
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

/**
 * URL-persisted pagination state for list pages.
 *
 * Reads `?{namespace}Page=` and `?{namespace}Size=` from the URL, slices the
 * caller's item list, and writes updates back to the URL. Deep links work.
 * Out-of-range page values clamp to [1, totalPages] automatically.
 *
 * For filter + sort state, use separate `useSearchParams()` reads in the
 * calling component and call `resetPage()` whenever a filter/sort changes.
 */
export function useListPagination<T>({
  items,
  namespace = 'p',
  defaultPageSize = 50,
  pageSizeOptions = DEFAULT_SIZES,
}: UseListPaginationOptions<T>): UseListPaginationResult<T> {
  const [searchParams, setSearchParams] = useSearchParams()
  const pageKey = `${namespace}Page`
  const sizeKey = `${namespace}Size`

  const rawPageSize = parsePositiveInt(searchParams.get(sizeKey), defaultPageSize)
  const pageSize = pageSizeOptions.includes(rawPageSize) ? rawPageSize : defaultPageSize
  const totalItems = items.length
  const totalPages = totalItems === 0 ? 1 : Math.max(1, Math.ceil(totalItems / pageSize))
  const rawPage = parsePositiveInt(searchParams.get(pageKey), 1)
  const page = Math.min(Math.max(1, rawPage), totalPages)

  const paginatedItems = useMemo(
    () => items.slice((page - 1) * pageSize, page * pageSize),
    [items, page, pageSize],
  )

  const setPage = useCallback(
    (nextPage: number) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (nextPage <= 1) next.delete(pageKey)
          else next.set(pageKey, String(nextPage))
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams, pageKey],
  )

  const setPageSize = useCallback(
    (nextSize: number) => {
      const clamped = pageSizeOptions.includes(nextSize) ? nextSize : defaultPageSize
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (clamped === defaultPageSize) next.delete(sizeKey)
          else next.set(sizeKey, String(clamped))
          // Reset to page 1 when page size changes.
          next.delete(pageKey)
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams, pageSizeOptions, defaultPageSize, sizeKey, pageKey],
  )

  const resetPage = useCallback(() => setPage(1), [setPage])

  return { page, pageSize, totalItems, totalPages, paginatedItems, setPage, setPageSize, resetPage }
}
