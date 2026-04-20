import { cn } from '@/lib/utils'
import type { PolicyFieldSource } from '@/api/types/ceremony-policy'

const SOURCE_STYLES: Record<PolicyFieldSource, string> = {
  project: 'bg-accent/10 text-accent',
  department: 'bg-success/10 text-success',
  default: 'bg-border text-text-muted',
}

const SOURCE_LABELS: Record<PolicyFieldSource, string> = {
  project: 'Project',
  department: 'Department',
  default: 'Default',
}

export interface PolicySourceBadgeProps {
  source: PolicyFieldSource
  className?: string
}

export function PolicySourceBadge({ source, className }: PolicySourceBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium uppercase tracking-wider',
        SOURCE_STYLES[source],
        className,
      )}
    >
      {SOURCE_LABELS[source]}
    </span>
  )
}
