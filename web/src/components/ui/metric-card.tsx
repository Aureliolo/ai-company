import { cn } from '@/lib/utils'
import { Sparkline } from './sparkline'

export interface MetricCardProps {
  label: string
  value: string | number
  change?: { value: number; direction: 'up' | 'down' }
  sparklineData?: number[]
  progress?: { current: number; total: number }
  subText?: string
  className?: string
}

export function MetricCard({
  label,
  value,
  change,
  sparklineData,
  progress,
  subText,
  className,
}: MetricCardProps) {
  const progressPct = progress && progress.total > 0
    ? Math.max(0, Math.min(100, Math.round((progress.current / progress.total) * 100)))
    : 0

  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-card p-card',
        'transition-colors duration-200',
        'hover:bg-card-hover',
        className,
      )}
    >
      {/* Top row: label + sparkline */}
      <div className="flex items-start justify-between">
        <span className="text-compact uppercase tracking-[0.06em] text-muted-foreground">
          {label}
        </span>
        {sparklineData && sparklineData.length > 1 && (
          <Sparkline data={sparklineData} width={60} height={28} />
        )}
      </div>

      {/* Value */}
      <div className="mt-1 font-mono text-metric font-bold leading-tight tracking-tight text-foreground" data-testid="metric-value">
        {value}
      </div>

      {/* Progress bar */}
      {progress && (
        <div
          role="progressbar"
          aria-valuenow={progressPct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label} progress`}
          className="mt-2 h-0.5 w-full overflow-hidden rounded-full bg-border"
        >
          <div
            className="h-full rounded-full bg-accent transition-all duration-[900ms]"
            style={{
              width: `${progressPct}%`,
              transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          />
        </div>
      )}

      {/* Bottom row: sub-text + change badge */}
      {(subText || change) && (
        <div className="mt-2 flex items-center justify-between">
          {subText && (
            <span className="text-xs text-muted-foreground">{subText}</span>
          )}
          {change && <ChangeBadge {...change} className={subText ? undefined : 'ml-auto'} />}
        </div>
      )}
    </div>
  )
}

function ChangeBadge({ value, direction, className }: { value: number; direction: 'up' | 'down'; className?: string }) {
  const isUp = direction === 'up'
  const label = isUp ? `Up ${value} percent` : `Down ${value} percent`

  return (
    <span
      aria-label={label}
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5',
        'font-mono text-compact font-medium',
        isUp
          ? 'bg-success/8 text-success border border-success/20'
          : 'bg-danger/8 text-danger border border-danger/20',
        className,
      )}
    >
      {isUp ? '+' : '-'}{value}%
    </span>
  )
}
