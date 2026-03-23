import type { FeedEvent } from "@/data/types.ts"

const actionColors: Record<string, string> = {
  complete: "var(--theme-accent)",
  approve: "var(--theme-success)",
  delegate: "#a78bfa",
  start: "var(--theme-accent)",
  submit: "#60a5fa",
  flag: "var(--theme-warning)",
  receive: "#60a5fa",
  tool: "#6b7280",
}

const actionLabels: Record<string, string> = {
  complete: "completed",
  approve: "approved",
  delegate: "delegated",
  start: "started",
  submit: "submitted",
  flag: "flagged",
  receive: "received",
  tool: "used tool",
}

interface ActivityStreamProps {
  events: FeedEvent[] | Array<{
    id: number
    time: string
    minutesAgo: number
    agent: string
    agentFull: string
    action: string
    task: string
    to: string | null
    toFull: string | null
    type: string
  }>
  compact?: boolean
}

export function ActivityStream({ events, compact }: ActivityStreamProps) {
  return (
    <div className="flex flex-col">
      {events.map((item, i) => (
        <div
          key={item.id}
          className="flex items-start gap-2.5 py-[7px] border-b border-border/50 last:border-0 fade-in-up"
          style={{ animationDelay: `${i * 30}ms` }}
        >
          {/* Timeline dot */}
          <div className="flex flex-col items-center shrink-0 pt-1">
            <div
              className="w-1.5 h-1.5 rounded-full shrink-0"
              style={{
                background: actionColors[item.type] ?? "var(--theme-text-muted)",
              }}
            />
            {i < events.length - 1 && (
              <div className="w-px flex-1 bg-border mt-1 min-h-3.5" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-1.5 flex-wrap">
              {!compact && (
                <span className="text-xs font-semibold text-text-primary shrink-0">
                  {item.agent}
                </span>
              )}
              <span
                className="text-[11px] shrink-0"
                style={{
                  color: actionColors[item.type] ?? "var(--theme-text-secondary)",
                }}
              >
                {compact ? item.action : (actionLabels[item.type] ?? item.action)}
              </span>
              {!compact && item.task && (
                <span className="text-xs text-text-secondary truncate">
                  {item.task}
                </span>
              )}
              {!compact && item.to && (
                <span className="text-[11px] text-text-muted shrink-0">
                  -&gt; {item.to}
                </span>
              )}
            </div>
          </div>

          <span className="text-[10px] font-mono text-text-muted shrink-0 pt-0.5 whitespace-nowrap">
            {item.time}
          </span>
        </div>
      ))}
    </div>
  )
}
