import { GitBranch } from 'lucide-react'
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
      className={cn(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-micro font-medium bg-accent/5 text-text-muted',
        className,
      )}
      title={tooltip}
      tabIndex={0}
      role="note"
      aria-label={tooltip}
    >
      <GitBranch className="size-2.5" aria-hidden />
      Controls {dependents.length}
    </span>
  )
}
