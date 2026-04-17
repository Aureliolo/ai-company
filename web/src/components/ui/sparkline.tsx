import { useId } from 'react'
import { cn } from '@/lib/utils'

export interface SparklineProps {
  data: number[]
  color?: string
  width?: number
  height?: number
  animated?: boolean
  className?: string
  /**
   * Accessible name for the chart. Required for standalone usage (the
   * sparkline becomes a labeled `role="img"` when set).
   *
   * When omitted, the sparkline is treated as decoration and emits
   * `aria-hidden="true"`. Use this mode when the chart is layered
   * beside a labeled sibling (for example, inside a `MetricCard`
   * whose `label` + `value` already carry the semantic meaning).
   */
  ariaLabel?: string
}

function buildPoints(data: number[], width: number, height: number): string {
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const padding = 2 // leave room for end dot

  return data
    .map((value, i) => {
      const x = padding + (i / (data.length - 1)) * (width - padding * 2)
      const y = height - padding - ((value - min) / range) * (height - padding * 2)
      return `${x},${y}`
    })
    .join(' ')
}

export function Sparkline({
  data,
  color = 'var(--so-accent)',
  width = 64,
  height = 24,
  animated = true,
  className,
  ariaLabel,
}: SparklineProps) {
  const gradientId = useId()

  if (data.length <= 1) return null

  const points = buildPoints(data, width, height)
  const pointPairs = points.split(' ')
  const lastPair = pointPairs[pointPairs.length - 1]!
  const [rawX, rawY] = lastPair.split(',')
  const lastX = parseFloat(rawX!)
  const lastY = parseFloat(rawY!)

  // Build polygon points for the fill area (line + bottom edge)
  const padding = 2
  const fillPoints = `${padding},${height - padding} ${points} ${width - padding},${height - padding}`

  // Approximate total path length for draw animation
  const approxPathLength = width * 1.5

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
      className={cn('shrink-0', className)}
      {...(ariaLabel
        ? { role: 'img' as const, 'aria-label': ariaLabel }
        : { 'aria-hidden': true as const }
      )}
    >
      {animated && (
        <style>{`
          @keyframes sparkline-draw {
            from { stroke-dashoffset: ${approxPathLength}; }
            to { stroke-dashoffset: 0; }
          }
          @keyframes sparkline-fade {
            from { opacity: 0; }
            to { opacity: 1; }
          }
          @media (prefers-reduced-motion: reduce) {
            .sparkline-line, .sparkline-fill, .sparkline-dot {
              animation: none !important;
            }
          }
        `}</style>
      )}

      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Fill area */}
      <polygon
        className="sparkline-fill"
        points={fillPoints}
        fill={`url(#${gradientId})`}
        style={animated ? { animation: 'sparkline-fade 200ms ease-out 200ms both' } : undefined}
      />

      {/* Line */}
      <polyline
        className="sparkline-line"
        points={points}
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        style={animated ? {
          strokeDasharray: approxPathLength,
          strokeDashoffset: 0,
          animation: `sparkline-draw 200ms ease-out 200ms both`,
        } : undefined}
      />

      {/* End dot */}
      <circle
        className="sparkline-dot"
        cx={lastX}
        cy={lastY}
        r="2"
        fill={color}
        style={animated ? { animation: 'sparkline-fade 200ms ease-out 400ms both' } : undefined}
      />
    </svg>
  )
}
