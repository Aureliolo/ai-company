import { ChevronRight, MoreHorizontal } from 'lucide-react'
import { Link } from 'react-router'
import { cn } from '@/lib/utils'

export interface BreadcrumbItem {
  label: string
  /** React Router path. Omit on the final (current) item. */
  to?: string
}

export interface BreadcrumbsProps {
  items: readonly BreadcrumbItem[]
  /** Collapse middle items with an ellipsis when length exceeds this threshold. Default 4. */
  maxItems?: number
  className?: string
}

/**
 * Breadcrumb navigation for deep detail pages.
 *
 * Uses React Router's `<Link>` for clickable ancestors and a plain `<span>`
 * for the terminal (current) item, with `aria-current="page"`. Wraps in
 * `<nav aria-label="Breadcrumb">` per WAI-ARIA authoring practices.
 *
 * When `items.length > maxItems`, middle items are collapsed into an
 * ellipsis node so the trail never wraps over two lines on narrow viewports.
 */
export function Breadcrumbs({ items, maxItems = 4, className }: BreadcrumbsProps) {
  if (items.length === 0) return null

  const collapsed = items.length > maxItems
  const visibleItems: Array<BreadcrumbItem | 'ellipsis'> = collapsed
    ? [items[0]!, 'ellipsis', ...items.slice(items.length - (maxItems - 2))]
    : [...items]

  return (
    <nav
      aria-label="Breadcrumb"
      className={cn('text-xs text-muted-foreground', className)}
    >
      <ol className="flex flex-wrap items-center gap-1.5">
        {visibleItems.map((item, idx) => {
          const isLast = idx === visibleItems.length - 1
          return (
            <li key={typeof item === 'string' ? `ellipsis-${idx}` : `${item.label}-${idx}`} className="flex items-center gap-1.5">
              {item === 'ellipsis' ? (
                <span aria-hidden="true" className="inline-flex items-center">
                  <MoreHorizontal className="size-3.5" />
                </span>
              ) : isLast ? (
                <span aria-current="page" className="font-medium text-foreground">
                  {item.label}
                </span>
              ) : item.to ? (
                <Link
                  to={item.to}
                  className="rounded px-0.5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                >
                  {item.label}
                </Link>
              ) : (
                <span>{item.label}</span>
              )}
              {!isLast && (
                <ChevronRight aria-hidden="true" className="size-3 shrink-0 text-muted-foreground/70" />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
