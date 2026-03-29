import { motion } from 'framer-motion'
import { cn, type AgentRuntimeStatus, type SemanticColor, getStatusColor } from '@/lib/utils'
import { useStatusTransition } from '@/hooks/useStatusTransition'

const STATUS_LABELS: Record<AgentRuntimeStatus, string> = {
  active: 'Active',
  idle: 'Idle',
  error: 'Error',
  offline: 'Offline',
}

const DOT_COLOR_CLASSES: Record<SemanticColor | 'text-secondary', string> = {
  success: 'bg-success',
  accent: 'bg-accent',
  warning: 'bg-warning',
  danger: 'bg-danger',
  'text-secondary': 'bg-text-secondary',
}

interface StatusBadgeProps {
  status: AgentRuntimeStatus
  label?: boolean
  pulse?: boolean
  className?: string
  /** Enable animated color transition on status change. Default: false. */
  animated?: boolean
}

export function StatusBadge({ status, label = false, pulse = false, className, animated = false }: StatusBadgeProps) {
  const color = getStatusColor(status)
  const statusLabel = STATUS_LABELS[status]
  const { motionProps } = useStatusTransition(status)

  return (
    <span
      className={cn('inline-flex items-center gap-1.5', className)}
      aria-label={statusLabel}
      role="status"
    >
      {animated ? (
        <motion.span
          data-slot="status-dot"
          className={cn(
            'size-1.5 shrink-0 rounded-full',
            pulse && 'animate-pulse',
          )}
          {...motionProps}
        />
      ) : (
        <span
          data-slot="status-dot"
          className={cn(
            'size-1.5 shrink-0 rounded-full',
            DOT_COLOR_CLASSES[color],
            pulse && 'animate-pulse',
          )}
        />
      )}
      {label && (
        <span className="text-xs text-text-secondary">{statusLabel}</span>
      )}
    </span>
  )
}
