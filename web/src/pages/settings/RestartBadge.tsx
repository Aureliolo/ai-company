import { RotateCcw } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface RestartBadgeProps {
  className?: string
}

export function RestartBadge({ className }: RestartBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium bg-warning/10 text-warning',
        className,
      )}
      title="Changes to this setting require a restart to take effect"
    >
      <RotateCcw className="size-2.5" aria-hidden />
      Restart
    </span>
  )
}
