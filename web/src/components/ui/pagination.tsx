import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import { useCallback, useId } from 'react'
import { cn } from '@/lib/utils'
import { Button } from './button'

export interface PaginationProps {
  /** 1-indexed current page. */
  page: number
  /** Items per page. */
  pageSize: number
  /** Total item count (client-side). Undefined signals unknown total (cursor mode placeholder). */
  total: number | undefined
  onPageChange: (page: number) => void
  onPageSizeChange?: (size: number) => void
  /** Available page size options. Default [20, 50, 100]. */
  pageSizeOptions?: readonly number[]
  /** Hide page size selector (when total is small or fixed). */
  hidePageSize?: boolean
  /** Aria label for the nav element. Default "Pagination". */
  ariaLabel?: string
  className?: string
}

const DEFAULT_PAGE_SIZE_OPTIONS = [20, 50, 100] as const

/**
 * Pagination control for list views.
 *
 * Client-side slice mode: pass `page` + `pageSize` + `total`; the caller
 * slices its own list. Keyboard shortcuts (when focused inside the nav):
 * - Left / PageUp: previous page
 * - Right / PageDown: next page
 * - Home: first page
 * - End: last page
 *
 * The component API is stable for cursor-based pagination: when OPS-1
 * ships cursor endpoints, call-sites can keep using `<Pagination>` and
 * swap the underlying data fetch without changing the control surface.
 */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
  hidePageSize = false,
  ariaLabel = 'Pagination',
  className,
}: PaginationProps) {
  const knownTotal = total !== undefined
  // Defensive clamp: pageSize must be positive to avoid division-by-zero in totalPages.
  const safePageSize = pageSize > 0 ? pageSize : DEFAULT_PAGE_SIZE_OPTIONS[0]!
  const totalPages = knownTotal && total > 0 ? Math.max(1, Math.ceil(total / safePageSize)) : 1
  // In cursor mode (total unknown) we cannot determine totalPages, so don't clamp down to 1.
  const safePage = knownTotal ? Math.min(Math.max(1, page), totalPages) : Math.max(1, page)
  const isFirst = safePage <= 1
  const isLastKnown = knownTotal && safePage >= totalPages
  // In cursor mode Next stays enabled (consumer controls flow); Last is disabled because
  // the total page count is not known to this control.
  const isNextDisabled = knownTotal ? isLastKnown : false
  const isLastJumpDisabled = knownTotal ? isLastKnown : true

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLElement>) => {
      switch (event.key) {
        case 'ArrowLeft':
        case 'PageUp':
          if (!isFirst) {
            event.preventDefault()
            onPageChange(safePage - 1)
          }
          break
        case 'ArrowRight':
        case 'PageDown':
          if (!isNextDisabled) {
            event.preventDefault()
            onPageChange(safePage + 1)
          }
          break
        case 'Home':
          if (!isFirst) {
            event.preventDefault()
            onPageChange(1)
          }
          break
        case 'End':
          if (!isLastJumpDisabled) {
            event.preventDefault()
            onPageChange(totalPages)
          }
          break
        default:
          break
      }
    },
    [isFirst, isNextDisabled, isLastJumpDisabled, onPageChange, safePage, totalPages],
  )

  const rangeStart = total === undefined ? undefined : total === 0 ? 0 : (safePage - 1) * safePageSize + 1
  const rangeEnd = total === undefined ? undefined : Math.min(safePage * safePageSize, total)
  const selectId = useId()

  return (
    <nav
      aria-label={ariaLabel}
      onKeyDown={onKeyDown}
      className={cn('flex flex-wrap items-center justify-between gap-3 text-xs', className)}
    >
      <div className="text-muted-foreground">
        {total === undefined
          ? `Page ${safePage}`
          : total === 0
            ? 'No items'
            : `${rangeStart}-${rangeEnd} of ${total}`}
      </div>

      <div className="flex items-center gap-2">
        {!hidePageSize && onPageSizeChange && (
          <div className="flex items-center gap-1.5">
            <label htmlFor={selectId} className="sr-only">
              Items per page
            </label>
            <select
              id={selectId}
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className={cn(
                'rounded-md border border-border bg-surface px-2 py-1 text-xs text-foreground',
                'focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent',
              )}
            >
              {pageSizeOptions.map((size) => (
                <option key={size} value={size}>
                  {size} / page
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="flex items-center gap-1">
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="First page"
            disabled={isFirst}
            onClick={() => onPageChange(1)}
          >
            <ChevronsLeft className="size-3.5" aria-hidden="true" />
          </Button>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Previous page"
            disabled={isFirst}
            onClick={() => onPageChange(safePage - 1)}
          >
            <ChevronLeft className="size-3.5" aria-hidden="true" />
          </Button>
          <span aria-current="page" className="px-2 tabular-nums text-foreground">
            {safePage}
            {total !== undefined && (
              <span className="text-muted-foreground"> / {totalPages}</span>
            )}
          </span>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Next page"
            disabled={isNextDisabled}
            onClick={() => onPageChange(safePage + 1)}
          >
            <ChevronRight className="size-3.5" aria-hidden="true" />
          </Button>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label="Last page"
            disabled={isLastJumpDisabled}
            onClick={() => onPageChange(totalPages)}
          >
            <ChevronsRight className="size-3.5" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </nav>
  )
}
