import { Link2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface DependencyIndicatorProps {
  /** Human-readable names of the dependent settings. */
  dependents: readonly string[]
  className?: string
}

export function DependencyIndicator({ dependents, className }: DependencyIndicatorProps) {
  if (dependents.length === 0) return null

  const tooltip = `Controls: ${dependents.join(', ')}`

  return (
    <span
      className={cn('inline-flex items-center text-text-muted', className)}
      title={tooltip}
      tabIndex={0}
      role="note"
      aria-label={tooltip}
    >
      <Link2 className="size-3" aria-hidden />
    </span>
  )
}
