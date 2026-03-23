import type { Department } from "@/data/types.ts"

interface DeptHealthBarProps {
  dept: Department
}

export function DeptHealthBar({ dept }: DeptHealthBarProps) {
  const isWarn = dept.health < 50
  const barColorClass = isWarn ? "bg-warning" : "bg-accent"
  const textColorClass = isWarn ? "text-warning" : "text-accent"

  return (
    <div className="grid items-center gap-3 py-2 border-b border-border/60 last:border-0"
      style={{ gridTemplateColumns: "110px 1fr 80px 80px 60px" }}
    >
      <span className="text-xs text-text-secondary font-medium truncate">
        {dept.name}
      </span>

      <div className="relative h-1.5 bg-border rounded-full">
        <div
          className={`absolute h-full ${barColorClass} rounded-full bar-animated`}
          style={{
            width: `${dept.health}%`,
            boxShadow: isWarn ? undefined : "0 0 8px var(--theme-accent-glow, rgba(34,211,238,0.3))",
          }}
        />
      </div>

      <span className={`text-xs font-mono ${textColorClass} font-semibold text-right`}>
        {dept.health}%
      </span>

      <span className="text-[11px] text-text-muted text-center">
        {dept.agents}a -- {dept.tasks}t
      </span>

      <span className="text-[11px] font-mono text-text-muted text-right">
        ${dept.cost.toFixed(2)}
      </span>
    </div>
  )
}
