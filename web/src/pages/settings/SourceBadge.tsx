import { cn } from '@/lib/utils'
import type { SettingSource } from '@/api/types'

const SOURCE_STYLES: Record<SettingSource, string> = {
  db: 'bg-accent/10 text-accent',
  env: 'bg-warning/10 text-warning',
  yaml: 'bg-success/10 text-success',
  default: 'bg-border text-text-muted',
}

const SOURCE_LABELS: Record<SettingSource, string> = {
  db: 'DB',
  env: 'ENV',
  yaml: 'YAML',
  default: 'Default',
}

export interface SourceBadgeProps {
  source: SettingSource
  className?: string
}

export function SourceBadge({ source, className }: SourceBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider',
        SOURCE_STYLES[source],
        className,
      )}
    >
      {SOURCE_LABELS[source]}
    </span>
  )
}
