import { cn, getHealthColor, type SemanticColor } from '@/lib/utils'

const COLOR_CLASSES: Record<SemanticColor, string> = {
  success: 'stroke-success',
  accent: 'stroke-accent',
  warning: 'stroke-warning',
  danger: 'stroke-danger',
}

const SIZE_CONFIG = {
  sm: { radius: 32, stroke: 6, valueSize: 'text-sm', labelSize: 'text-micro' },
  md: { radius: 48, stroke: 6, valueSize: 'text-lg', labelSize: 'text-compact' },
} as const

interface ProgressGaugeProps {
  value: number
  max?: number
  label?: string
  size?: 'sm' | 'md'
  className?: string
}

export function ProgressGauge({
  value,
  max = 100,
  label,
  size = 'md',
  className,
}: ProgressGaugeProps) {
  const safeMax = Number.isFinite(max) ? Math.max(max, 1) : 1
  const safeValue = Number.isFinite(value) ? value : 0
  const clampedValue = Math.max(0, Math.min(safeValue, safeMax))
  const percentage = Math.round((clampedValue / safeMax) * 100)
  const color = getHealthColor(percentage)
  const config = SIZE_CONFIG[size]

  // SVG arc geometry for a 180-degree half-circle (bottom open)
  const { radius, stroke } = config
  const svgWidth = (radius + stroke) * 2
  const svgHeight = radius + stroke * 2
  const cx = svgWidth / 2
  const cy = radius + stroke

  // Arc circumference (half circle)
  const circumference = Math.PI * radius
  const filledLength = (percentage / 100) * circumference
  const dashOffset = circumference - filledLength

  return (
    <div
      role="meter"
      aria-valuenow={percentage}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ? `${label}: ${percentage}%` : `${percentage}%`}
      className={cn('inline-flex flex-col items-center', className)}
    >
      <svg
        width={svgWidth}
        height={svgHeight}
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        className="overflow-visible"
      >
        {/* Track */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          strokeWidth={stroke}
          className="stroke-border"
          strokeLinecap="round"
        />
        {/* Fill */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          strokeWidth={stroke}
          className={cn(COLOR_CLASSES[color], 'transition-all duration-[900ms]')}
          style={{
            strokeDasharray: circumference,
            strokeDashoffset: dashOffset,
            transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
          }}
          strokeLinecap="round"
        />
        {/* Center value */}
        <text
          x={cx}
          y={cy - (size === 'md' ? 12 : 8)}
          textAnchor="middle"
          className={cn('fill-foreground font-mono font-bold', config.valueSize)}
        >
          {percentage}%
        </text>
      </svg>
      {label && (
        <span className={cn('text-muted-foreground', config.labelSize)}>
          {label}
        </span>
      )}
    </div>
  )
}
