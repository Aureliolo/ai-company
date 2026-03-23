import { useTheme } from "@/themes/provider.tsx"
import { company } from "@/data/index.ts"

function Divider() {
  return <span className="w-px h-3 bg-border shrink-0" />
}

function Dot({ color, pulse }: { color: string; pulse?: boolean }) {
  return (
    <span
      className={`inline-block w-[5px] h-[5px] rounded-full mr-1.5 shrink-0 ${pulse ? "status-pulse" : ""}`}
      style={{ background: color, "--pulse-color": color } as React.CSSProperties}
    />
  )
}

export function StatusBar() {
  const theme = useTheme()
  const accentColor = theme.colors.accent
  const successColor = theme.colors.success
  const warningColor = theme.colors.warning

  const budgetColor =
    company.budgetPercent > 80
      ? theme.colors.danger
      : company.budgetPercent > 60
        ? warningColor
        : accentColor

  return (
    <div className="bg-bg-base border-b border-border px-6 h-8 flex items-center gap-6 shrink-0 text-[11px] tracking-wide font-mono text-text-secondary select-none">
      <span className="text-text-muted text-[10px] uppercase tracking-widest">
        {company.name}
      </span>

      <Divider />

      <span className="flex items-center whitespace-nowrap">
        <Dot color={accentColor} pulse={theme.animation.statusPulse} />
        {company.totalAgents} agents
      </span>

      <span className="flex items-center whitespace-nowrap">
        <Dot color={successColor} />
        {company.activeAgents} active
      </span>

      <span className="flex items-center whitespace-nowrap">
        <Dot color={warningColor} pulse={theme.animation.statusPulse} />
        {company.tasksRunning} tasks running
      </span>

      <Divider />

      <span className="flex items-center whitespace-nowrap">
        <span className="text-text-muted">spend</span>
        <span className="text-text-primary ml-1.5">
          ${company.spentToday.toFixed(2)}
        </span>
        <span className="text-text-muted ml-1">today</span>
      </span>

      <span className="flex items-center whitespace-nowrap">
        <span className="text-text-muted">budget</span>
        <span className="ml-1.5" style={{ color: budgetColor }}>
          {company.budgetPercent}%
        </span>
        <span className="text-text-muted ml-1">used</span>
      </span>

      <div className="flex-1" />

      <span className="flex items-center whitespace-nowrap">
        <Dot color={warningColor} />
        {company.pendingApprovals} pending approvals
      </span>

      <Divider />

      <span className="flex items-center whitespace-nowrap">
        <span className="text-success mr-1">*</span>
        <span className="text-text-muted">all systems nominal</span>
      </span>
    </div>
  )
}
