import { useEffect, useRef } from 'react'
import { Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface OrgChartSearchOverlayProps {
  open: boolean
  query: string
  onQueryChange: (value: string) => void
  onClose: () => void
  /** Number of nodes matching the current query. */
  matchCount: number
}

/**
 * Floating search overlay for filtering the org chart.
 *
 * Opens with Ctrl+F / Cmd+F (wired in OrgChartPage).  While open,
 * matching nodes remain bright and non-matching nodes dim -- the
 * filter is applied by OrgChartPage via the same highlighted-nodes
 * mechanism that powers hover-chain highlighting.
 *
 * Close with Escape or the × button.
 */
export function OrgChartSearchOverlay({
  open,
  query,
  onQueryChange,
  onClose,
  matchCount,
}: OrgChartSearchOverlayProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      // Defer focus to the next frame so the input is actually
      // mounted and visible before we try to focus it.
      const id = requestAnimationFrame(() => {
        inputRef.current?.focus()
        inputRef.current?.select()
      })
      return () => cancelAnimationFrame(id)
    }
    return undefined
  }, [open])

  if (!open) return null

  return (
    <div
      className={cn(
        'absolute left-1/2 top-4 z-10 -translate-x-1/2',
        'flex items-center gap-2 rounded-lg border border-border bg-card/95 px-3 py-2 shadow-lg backdrop-blur',
        'min-w-[320px] max-w-[480px]',
      )}
      role="search"
    >
      <Search className="size-4 shrink-0 text-text-muted" aria-hidden="true" />
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            e.preventDefault()
            onClose()
          }
        }}
        placeholder="Search agents, roles, departments..."
        aria-label="Search org chart"
        className="min-w-0 flex-1 bg-transparent text-sm text-foreground placeholder:text-text-muted focus:outline-none"
      />
      {query.length > 0 && (
        <span
          className="font-mono text-micro text-text-muted"
          aria-live="polite"
        >
          {matchCount} match{matchCount === 1 ? '' : 'es'}
        </span>
      )}
      <button
        type="button"
        onClick={onClose}
        aria-label="Close search"
        className="rounded p-0.5 text-text-muted transition-colors hover:bg-border/40 hover:text-foreground"
      >
        <X className="size-3.5" />
      </button>
    </div>
  )
}
