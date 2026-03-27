import { cn } from '@/lib/utils'
import type { ProviderHealthStatus } from '@/api/types'
import { getProviderHealthColor } from '@/utils/providers'
import type { SemanticColor } from '@/lib/utils'

const STATUS_LABELS: Record<ProviderHealthStatus, string> = {
  up: 'Up',
  degraded: 'Degraded',
  down: 'Down',
}

const DOT_COLOR_CLASSES: Record<SemanticColor, string> = {
  success: 'bg-success',
  accent: 'bg-accent',
  warning: 'bg-warning',
  danger: 'bg-danger',
}

export interface ProviderHealthBadgeProps {
  status: ProviderHealthStatus
  label?: boolean
  pulse?: boolean
  className?: string
}

/**
 * Provider health status indicator (up/degraded/down colored dot + optional label).
 *
 * Uses the same visual pattern as StatusBadge but with provider-specific health
 * status types and color mapping (up=success, degraded=warning, down=danger).
 */
export function ProviderHealthBadge({
  status,
  label = false,
  pulse = false,
  className,
}: ProviderHealthBadgeProps) {
  const color = getProviderHealthColor(status)
  const statusLabel = STATUS_LABELS[status]

  return (
    <span
      className={cn('inline-flex items-center gap-1.5', className)}
      aria-label={statusLabel}
    >
      <span
        data-slot="health-dot"
        className={cn(
          'size-1.5 shrink-0 rounded-full',
          DOT_COLOR_CLASSES[color],
          pulse && 'animate-pulse',
        )}
      />
      {label && (
        <span className="text-xs text-text-secondary">{statusLabel}</span>
      )}
    </span>
  )
}
