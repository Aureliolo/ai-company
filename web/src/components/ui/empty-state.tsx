import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './button'

export interface EmptyStateAction {
  label: string
  onClick: () => void
  variant?: 'default' | 'outline'
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
  className,
  announce = false,
}: EmptyStateProps) {
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
