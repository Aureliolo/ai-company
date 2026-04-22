import type { LucideIcon } from 'lucide-react'
import { ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './button'

// Protocols allowed in learnMore.href. Anything else (including
// javascript:, data:, vbscript:, file:) is stripped because the consumer
// passes an href straight to <a href=...>.
const SAFE_HREF_PATTERN = /^(https?:|mailto:|tel:|\/|#)/i

export interface EmptyStateAction {
  label: string
  onClick: () => void
  variant?: 'default' | 'outline'
}

export interface EmptyStateLearnMore {
  label?: string
  /** Internal React Router path (onClick handled by the caller if routing is needed) or external URL. */
  href: string
  /** Set true when href points outside the app; adds `target=_blank` + `rel=noopener`. Default auto-detects based on protocol. */
  external?: boolean
}

export interface EmptyStateProps {
  /** Optional icon displayed above the title. */
  icon?: LucideIcon
  /** Primary message. */
  title: string
  /** Optional supporting text. */
  description?: string
  /** Optional action button. */
  action?: EmptyStateAction
  /** Optional "Learn more" link rendered below the description. Use for contextual help. */
  learnMore?: EmptyStateLearnMore
  className?: string
  /** Enable live-region announcements for dynamic state changes. Default: false. */
  announce?: boolean
}

/**
 * Empty state placeholder for sections with no data.
 *
 * Centers within its parent container with muted styling.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  learnMore,
  className,
  announce = false,
}: EmptyStateProps) {
  // Strip any href with an unsafe protocol (javascript:, data:, vbscript:,
  // file:, ...) before we render <a href=...>. Internal paths starting with
  // `/` or `#` and conventional protocols (http/https/mailto/tel) are
  // allowed. Callers needing client-side routing for internal paths can pass
  // an explicit `onClick` (or wrap EmptyState in a custom link-based shell).
  // Normalise once so the protocol check, the internal/external classification,
  // and the rendered `href` all see the same string.
  const normalizedHref = learnMore?.href.trim()
  const safeLearnMore =
    learnMore !== undefined && normalizedHref !== undefined && SAFE_HREF_PATTERN.test(normalizedHref)
      ? { ...learnMore, href: normalizedHref }
      : undefined
  const isExternal =
    safeLearnMore !== undefined &&
    (safeLearnMore.external ??
      (safeLearnMore.href.startsWith('http://') ||
        safeLearnMore.href.startsWith('https://') ||
        safeLearnMore.href.startsWith('//')))

  return (
    <div
      role={announce ? 'status' : undefined}
      aria-live={announce ? 'polite' : undefined}
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-12 text-center',
        className,
      )}
    >
      {Icon && (
        <Icon
          className="size-10 text-muted-foreground"
          strokeWidth={1.5}
          aria-hidden="true"
        />
      )}
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description && (
          <p className="max-w-sm text-xs text-muted-foreground">{description}</p>
        )}
        {safeLearnMore && (
          <a
            href={safeLearnMore.href}
            target={isExternal ? '_blank' : undefined}
            rel={isExternal ? 'noopener noreferrer' : undefined}
            className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded-sm"
          >
            {safeLearnMore.label ?? 'Learn more'}
            {isExternal && <ExternalLink className="size-3" aria-hidden="true" />}
          </a>
        )}
      </div>
      {action && (
        <Button
          variant={action.variant ?? 'outline'}
          size="sm"
          onClick={action.onClick}
          className="mt-1"
        >
          {action.label}
        </Button>
      )}
    </div>
  )
}
