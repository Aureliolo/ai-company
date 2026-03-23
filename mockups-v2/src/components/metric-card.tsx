import { motion } from "framer-motion"
import { useTheme } from "@/themes/provider.tsx"
import { Sparkline } from "./sparkline.tsx"

interface MetricCardProps {
  label: string
  value: string
  sub?: string
  change?: string
  changePositive?: boolean
  trend: number[]
  trendColor?: string
  subColor?: string
  progressValue?: number
  progressColor?: string
}

export function MetricCard({
  label,
  value,
  sub,
  change,
  changePositive,
  trend,
  trendColor = "var(--theme-accent)",
  subColor = "text-text-muted",
  progressValue,
  progressColor,
}: MetricCardProps) {
  const theme = useTheme()
  const { density, animation } = theme

  return (
    <motion.div
      variants={animation.cardEntrance}
      whileHover={animation.hoverLift ?? undefined}
      className={`bg-bg-card border border-border rounded-lg ${density.cardPadding} flex flex-col gap-2 transition-colors`}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className={`${density.fontSize.label} text-text-muted uppercase tracking-widest mb-1.5`}>
            {label}
          </div>
          <div
            className={`${density.fontSize.metric} font-bold text-text-primary font-mono leading-none tracking-tight`}
          >
            {value}
          </div>
        </div>
        <Sparkline
          data={trend}
          color={trendColor}
          width={60}
          height={28}
          animated={animation.profile !== "instant"}
        />
      </div>

      {progressValue !== undefined && progressColor && (
        <div className="h-0.5 bg-border rounded-sm overflow-hidden">
          <div
            className="h-full rounded-sm bar-animated"
            style={{
              width: `${progressValue}%`,
              background: progressColor,
            }}
          />
        </div>
      )}

      <div className="flex items-center justify-between">
        {sub && (
          <span className={`${density.fontSize.body} ${subColor}`}>{sub}</span>
        )}
        {change && (
          <span
            className={`${density.fontSize.small} font-mono px-1.5 py-0.5 rounded ${
              changePositive
                ? "text-success bg-success/[0.08] border border-success/20"
                : "text-danger bg-danger/[0.08] border border-danger/20"
            }`}
          >
            {change}
          </span>
        )}
      </div>
    </motion.div>
  )
}
