import { useId } from 'react'
import { cn } from '@/lib/utils'

interface SparklineProps {
  data: number[]
  color?: string
  width?: number
  height?: number
  className?: string
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
  className,
}: SparklineProps) {
  const gradientId = useId()

  if (data.length === 0) return null

  const points = buildPoints(data, width, height)
  const pointPairs = points.split(' ')
  const lastPair = pointPairs[pointPairs.length - 1]!
  const [rawX, rawY] = lastPair.split(',')
  const lastX = parseFloat(rawX!)
  const lastY = parseFloat(rawY!)

  // Build polygon points for the fill area (line + bottom edge)
  const padding = 2
  const fillPoints = `${padding},${height - padding} ${points} ${width - padding},${height - padding}`

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
      className={cn('shrink-0', className)}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Fill area */}
      <polygon
        points={fillPoints}
        fill={`url(#${gradientId})`}
      />

      {/* Line */}
      <polyline
        points={points}
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />

      {/* End dot */}
      <circle
        cx={lastX}
        cy={lastY}
        r="2"
        fill={color}
      />
    </svg>
  )
}
