import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts"
import { useId } from "react"
import { useTheme } from "@/themes/provider.tsx"
import type { BudgetDay } from "@/data/types.ts"

interface BudgetChartProps {
  data: BudgetDay[]
  summary: {
    remaining: number
    percentUsed: number
    daysLeft: number
    projectedTotal: number
  }
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ value: number; name: string; color: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-bg-card border border-border-bright rounded-md px-3 py-2 text-[11px] font-mono">
      <div className="text-text-muted mb-1">{label}</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name === "actual" ? "Actual" : "Forecast"}: ${p.value?.toFixed(2)}
        </div>
      ))}
    </div>
  )
}

export function BudgetChart({ data, summary }: BudgetChartProps) {
  const theme = useTheme()
  const actualId = useId()
  const forecastId = useId()
  const accentColor = theme.colors.accent
  const warningColor = theme.colors.warning

  return (
    <div>
      <div className="flex gap-6 mb-3 text-[11px] font-mono">
        <div>
          <span className="text-text-muted">remaining </span>
          <span className="text-accent font-semibold">
            ${summary.remaining.toFixed(0)} ({100 - summary.percentUsed}%)
          </span>
        </div>
        <div>
          <span className="text-text-muted">at this rate </span>
          <span className="text-warning font-semibold">
            ~{summary.daysLeft.toFixed(1)} days left
          </span>
        </div>
      </div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
          >
            <defs>
              <linearGradient id={actualId} x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={accentColor}
                  stopOpacity={0.15}
                />
                <stop
                  offset="95%"
                  stopColor={accentColor}
                  stopOpacity={0}
                />
              </linearGradient>
              <linearGradient id={forecastId} x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={warningColor}
                  stopOpacity={0.08}
                />
                <stop
                  offset="95%"
                  stopColor={warningColor}
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="day"
              tick={{
                fontSize: 10,
                fill: theme.colors.textMuted,
                fontFamily: "var(--theme-font-mono)",
              }}
              axisLine={{ stroke: theme.colors.border }}
              tickLine={false}
              interval={4}
            />
            <YAxis
              tick={{
                fontSize: 10,
                fill: theme.colors.textMuted,
                fontFamily: "var(--theme-font-mono)",
              }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `$${v}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              x="Mar 23"
              stroke={theme.colors.borderBright}
              strokeDasharray="3 3"
              label={{
                value: "today",
                fill: theme.colors.textMuted,
                fontSize: 9,
                fontFamily: "var(--theme-font-mono)",
              }}
            />
            <Area
              type="monotone"
              dataKey="actual"
              name="actual"
              stroke={accentColor}
              strokeWidth={2}
              fill={`url(#${actualId})`}
              connectNulls={false}
              dot={false}
              activeDot={{ r: 3, fill: accentColor }}
            />
            <Area
              type="monotone"
              dataKey="forecast"
              name="forecast"
              stroke={warningColor}
              strokeWidth={1.5}
              strokeDasharray="4 3"
              fill={`url(#${forecastId})`}
              connectNulls={false}
              dot={false}
              activeDot={{ r: 3, fill: warningColor }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="flex gap-4 mt-2 text-[10px] text-text-muted font-mono">
        <span>
          <span className="text-accent">--</span> Actual spend
        </span>
        <span>
          <span className="text-warning">- -</span> Forecast
        </span>
        <span className="ml-auto">Budget: $2,400/mo</span>
      </div>
    </div>
  )
}
