const colorClasses: Record<string, string> = {
  accent: "text-accent",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
}

interface PerfMetricProps {
  label: string
  value: string
  unit?: string
  color?: string
}

export function PerfMetric({ label, value, unit, color = "accent" }: PerfMetricProps) {
  return (
    <div className="bg-bg-surface border border-border rounded-md px-3 py-2.5">
      <div className="text-[10px] text-text-muted mb-1 uppercase tracking-wide">
        {label}
      </div>
      <div className={`text-xl font-bold font-mono leading-none ${colorClasses[color] ?? "text-accent"}`}>
        {value}
        {unit && (
          <span className="text-xs font-normal text-text-muted ml-0.5">
            {unit}
          </span>
        )}
      </div>
    </div>
  )
}
