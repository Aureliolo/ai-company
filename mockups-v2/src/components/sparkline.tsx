import { useId } from "react"

interface SparklineProps {
  data: number[]
  width?: number
  height?: number
  color?: string
  fillOpacity?: number
  animated?: boolean
}

export function Sparkline({
  data,
  width = 64,
  height = 24,
  color = "var(--theme-accent)",
  fillOpacity = 0.1,
  animated = true,
}: SparklineProps) {
  const gradientId = useId()

  if (!data || data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  const pad = 1
  const w = width - pad * 2
  const h = height - pad * 2

  const points = data.map((v, i) => ({
    x: pad + (i / (data.length - 1)) * w,
    y: pad + h - ((v - min) / range) * h,
  }))

  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(" ")

  const areaPath =
    linePath +
    ` L${points[points.length - 1].x.toFixed(2)},${(pad + h).toFixed(2)}` +
    ` L${points[0].x.toFixed(2)},${(pad + h).toFixed(2)} Z`

  const last = points[points.length - 1]

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible shrink-0"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={fillOpacity * 3} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} />
      <path
        className={animated ? "sparkline-path" : ""}
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={animated ? undefined : { strokeDasharray: "none", strokeDashoffset: 0 }}
      />
      <circle cx={last.x} cy={last.y} r={2} fill={color} />
    </svg>
  )
}
