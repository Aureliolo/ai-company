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

function sanitizePositiveInt(value: number, fallback: number): number {
  const floored = Math.floor(value)
  return Number.isFinite(floored) && floored > 0 ? floored : fallback
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

  // Coerce caller-supplied sizes to positive integers. Read and write paths
  // share the same sanitised set so `slice()`, `totalPages`, and the URL
  // never disagree about page boundaries when a fractional or non-finite
  // option slips in (e.g. `12.5` or `NaN`).
  const safeDefaultPageSize = sanitizePositiveInt(defaultPageSize, 50)
  const sanitizedOptions = useMemo(() => {
    const set = new Set<number>()
    for (const option of pageSizeOptions) {
      const sanitized = sanitizePositiveInt(option, 0)
      if (sanitized > 0) set.add(sanitized)
    }
    // Guarantee the effective default is always part of the allowed set.
    set.add(safeDefaultPageSize)
    return [...set]
  }, [pageSizeOptions, safeDefaultPageSize])
  const rawPageSize = parsePositiveInt(searchParams.get(sizeKey), safeDefaultPageSize)
  const pageSize = sanitizedOptions.includes(rawPageSize) ? rawPageSize : safeDefaultPageSize
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
      const nextSanitized = sanitizePositiveInt(nextSize, safeDefaultPageSize)
      const clamped = sanitizedOptions.includes(nextSanitized) ? nextSanitized : safeDefaultPageSize
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          const previousSize = parsePositiveInt(prev.get(sizeKey), safeDefaultPageSize)
          const previousEffective = sanitizedOptions.includes(previousSize)
            ? previousSize
            : safeDefaultPageSize
          if (clamped === safeDefaultPageSize) next.delete(sizeKey)
          else next.set(sizeKey, String(clamped))
          // Only reset to page 1 when the effective page size actually changes;
          // idempotent setPageSize(sameSize) calls should not bounce the reader
          // back to page 1.
          if (clamped !== previousEffective) next.delete(pageKey)
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams, sanitizedOptions, safeDefaultPageSize, sizeKey, pageKey],
  )

  const resetPage = useCallback(() => setPage(1), [setPage])

  return { page, pageSize, totalItems, totalPages, paginatedItems, setPage, setPageSize, resetPage }
}
