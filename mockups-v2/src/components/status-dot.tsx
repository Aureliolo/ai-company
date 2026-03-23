import { useTheme } from "@/themes/provider.tsx"
import type { AgentStatus } from "@/data/types.ts"

const statusColors: Record<AgentStatus, string> = {
  active: "var(--theme-accent)",
  idle: "var(--theme-text-muted)",
  warning: "var(--theme-warning)",
  error: "var(--theme-danger)",
  onboarding: "#60a5fa",
}

interface StatusDotProps {
  status: AgentStatus
  size?: number
}

export function StatusDot({ status, size = 7 }: StatusDotProps) {
  const theme = useTheme()
  const color = statusColors[status]
  const shouldPulse = theme.animation.statusPulse && status === "active"

  return (
    <span
      className={`inline-block rounded-full shrink-0 ${shouldPulse ? "status-pulse" : ""}`}
      style={{
        width: size,
        height: size,
        background: color,
        "--pulse-color": color,
      } as React.CSSProperties}
    />
  )
}
