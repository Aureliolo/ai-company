import { cn, getHealthColor, type SemanticColor } from '@/lib/utils'

const BAR_COLOR_CLASSES: Record<SemanticColor, string> = {
  success: 'bg-success',
  accent: 'bg-accent',
  warning: 'bg-warning',
  danger: 'bg-danger',
}

interface DeptHealthBarProps {
  name: string
  health: number
  agentCount: number
  taskCount: number
  className?: string
}

export function DeptHealthBar({
  name,
  health,
  agentCount,
  taskCount,
  className,
}: DeptHealthBarProps) {
  const clamped = Math.max(0, Math.min(health, 100))
  const color = getHealthColor(clamped)

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {/* Header row */}
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-foreground">{name}</span>
        <span className="font-mono text-xs font-semibold text-foreground">{clamped}%</span>
      </div>

      {/* Health bar */}
      <div
        role="meter"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${name} health: ${clamped}%`}
        className="h-1.5 w-full overflow-hidden rounded-full bg-border"
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-[900ms]',
            BAR_COLOR_CLASSES[color],
          )}
          style={{
            width: `${clamped}%`,
            transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        />
      </div>

      {/* Stats row */}
      <div className="flex gap-3 text-xs text-muted-foreground">
        <span>{agentCount} {agentCount === 1 ? 'agent' : 'agents'}</span>
        <span>{taskCount} {taskCount === 1 ? 'task' : 'tasks'}</span>
      </div>
    </div>
  )
}
