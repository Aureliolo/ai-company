import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, Info, WifiOff, X, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './button'

export type ErrorBannerSeverity = 'error' | 'warning' | 'info'
export type ErrorBannerVariant = 'inline' | 'section' | 'offline'

export interface ErrorBannerProps {
  /** Layout density. `section` is the default page-level banner; `inline` is compact for form rows/cards; `offline` is the connectivity variant. */
  variant?: ErrorBannerVariant
  /** Color + ARIA role mapping. `error` uses role=alert, `warning`/`info` use role=status. Ignored when variant='offline' (forces warning). */
  severity?: ErrorBannerSeverity
  title: string
  description?: string | React.ReactNode
  /** When provided, renders a Retry button that invokes this handler. */
  onRetry?: () => void
  /** When provided, renders a Dismiss (X) button that invokes this handler. */
  onDismiss?: () => void
  /** Override the default icon (by severity). Always rendered at h-4 w-4 for consistency. */
  icon?: LucideIcon
  /** Optional action label shown next to Retry (e.g. "Learn more" link). */
  action?: { label: string; onClick: () => void } | React.ReactNode
  className?: string
}

const SEVERITY_ICON: Record<ErrorBannerSeverity, LucideIcon> = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const SEVERITY_STYLES: Record<ErrorBannerSeverity, string> = {
  error: 'border-danger/30 bg-danger/5 text-danger',
  warning: 'border-warning/30 bg-warning/5 text-warning',
  info: 'border-accent/30 bg-accent/5 text-accent',
}

/**
 * Shared error / warning / info banner for list fetch failures, offline
 * state, onboarding retry guidance, and form-level errors.
 *
 * For mutation errors use the toast store; for unrecoverable render errors
 * use `ErrorBoundary` with `level='section'`. See web/CLAUDE.md for the
 * full error-surface policy.
 */
export function ErrorBanner({
  variant = 'section',
  severity: severityProp = 'error',
  title,
  description,
  onRetry,
  onDismiss,
  icon,
  action,
  className,
}: ErrorBannerProps) {
  const severity: ErrorBannerSeverity = variant === 'offline' ? 'warning' : severityProp
  const Icon = icon ?? (variant === 'offline' ? WifiOff : SEVERITY_ICON[severity])

  const role = severity === 'error' ? 'alert' : 'status'
  const ariaLive = severity === 'error' ? 'assertive' : 'polite'

  const densityClasses = variant === 'inline' ? 'gap-2 px-3 py-2 text-xs' : 'gap-3 p-card text-sm'

  return (
    <div
      role={role}
      aria-live={ariaLive}
      className={cn(
        'flex items-start rounded-lg border',
        SEVERITY_STYLES[severity],
        densityClasses,
        className,
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" strokeWidth={1.75} />

      <div className="min-w-0 flex-1">
        <p className={cn('font-medium', variant === 'inline' ? 'text-xs' : 'text-sm')}>
          {title}
        </p>
        {description && (
          <p className={cn(
            'mt-1 text-muted-foreground',
            variant === 'inline' ? 'text-xs' : 'text-xs',
          )}>
            {description}
          </p>
        )}
        {(onRetry || action) && (
          <div className="mt-2 flex flex-wrap gap-2">
            {onRetry && (
              <Button size="xs" variant="outline" onClick={onRetry}>
                Retry
              </Button>
            )}
            {action && (typeof action === 'object' && action !== null && 'label' in action ? (
              <Button size="xs" variant="ghost" onClick={action.onClick}>
                {action.label}
              </Button>
            ) : action)}
          </div>
        )}
      </div>

      {onDismiss && (
        <Button
          size="icon-xs"
          variant="ghost"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="shrink-0 -mt-0.5 -mr-1"
        >
          <X className="size-3" aria-hidden="true" />
        </Button>
      )}
    </div>
  )
}
