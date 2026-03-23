import type { TaskEntry } from "@/data/types.ts"

const taskTypeColors: Record<string, string> = {
  research: "#60a5fa",
  analysis: "#a78bfa",
  report: "#34d399",
  development: "var(--theme-accent)",
  review: "#f472b6",
  operations: "#6b7280",
  design: "#fb923c",
  outreach: "#22d3ee",
}

interface TaskBarProps {
  task: TaskEntry
  maxEnd: number
}

export function TaskBar({ task, maxEnd }: TaskBarProps) {
  const safeMaxEnd = maxEnd > 0 ? maxEnd : 1
  const leftPct = (task.start / safeMaxEnd) * 100
  const widthPct = Math.max((task.duration / safeMaxEnd) * 100, 1.5)
  const color = task.completed
    ? taskTypeColors[task.type] ?? "var(--theme-accent)"
    : "var(--theme-warning)"

  return (
    <div className="flex items-center gap-2">
      <div className="w-[88px] text-[10px] text-text-muted truncate shrink-0 text-right">
        {task.name.length > 14 ? task.name.slice(0, 14) + "..." : task.name}
      </div>
      <div className="flex-1 relative h-5 bg-white/[0.02] rounded-sm">
        <div
          className={`absolute h-full rounded-sm flex items-center overflow-hidden ${!task.completed ? "task-current" : ""}`}
          style={{
            left: `${leftPct}%`,
            width: `${widthPct}%`,
            background: color,
            opacity: task.completed ? 0.65 : 1,
            boxShadow: !task.completed
              ? `0 0 8px color-mix(in srgb, ${color} 40%, transparent)`
              : undefined,
          }}
        >
          <span className="text-[9px] text-black/65 font-semibold pl-1 whitespace-nowrap">
            {task.duration}h
          </span>
        </div>
      </div>
      <span
        className={`text-[10px] w-4 text-center font-mono shrink-0 ${
          task.completed ? "text-text-muted" : "text-warning"
        }`}
      >
        {task.completed ? "v" : ">"}
      </span>
    </div>
  )
}
