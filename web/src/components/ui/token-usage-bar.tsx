import { cn } from '@/lib/utils'

export interface TokenSegment {
  label: string
  value: number
  color?: string
}

interface TokenUsageBarProps {
  segments: readonly TokenSegment[]
  total: number
  className?: string
}

const SEGMENT_COLORS = [
  'bg-accent',
  'bg-success',
  'bg-warning',
  'bg-danger',
  'bg-accent-dim',
] as const

export function TokenUsageBar({ segments, total, className }: TokenUsageBarProps) {
  const usedTokens = segments.reduce((sum, s) => sum + s.value, 0)
  const usedPercent = total > 0 ? Math.min(100, (usedTokens / total) * 100) : 0

  return (
    <div
      role="meter"
      aria-valuenow={usedTokens}
      aria-valuemin={0}
      aria-valuemax={total}
      aria-label={`Token usage: ${usedTokens.toLocaleString()} of ${total.toLocaleString()}`}
      className={cn('flex flex-col gap-1', className)}
    >
      <div className="h-2 w-full overflow-hidden rounded-full bg-border">
        <div className="flex h-full" style={{ width: `${usedPercent}%` }}>
          {segments.map((segment, i) => {
            const segPercent = total > 0 ? (segment.value / total) * 100 : 0
            if (segPercent <= 0) return null
            const colorClass = segment.color ?? SEGMENT_COLORS[i % SEGMENT_COLORS.length]
            return (
              <div
                key={segment.label}
                className={cn(
                  'h-full transition-all duration-[900ms]',
                  colorClass,
                  i === 0 && 'rounded-l-full',
                  i === segments.length - 1 && 'rounded-r-full',
                )}
                style={{
                  width: `${(segment.value / usedTokens) * 100}%`,
                  transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
                }}
                title={`${segment.label}: ${segment.value.toLocaleString()} tokens`}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}
