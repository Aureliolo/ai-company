import type { CareerEvent as CareerEventType } from "@/data/types.ts"

const typeColors: Record<string, string> = {
  hire: "var(--theme-success)",
  promote: "var(--theme-accent)",
  milestone: "var(--theme-warning)",
  reassign: "var(--theme-accent-dim)",
  "trust-upgrade": "var(--theme-text-secondary)",
}

interface CareerEventProps {
  event: CareerEventType
  isLast: boolean
}

export function CareerEvent({ event, isLast }: CareerEventProps) {
  const dotColor = typeColors[event.type] ?? "var(--theme-text-muted)"

  return (
    <div className={`flex gap-2.5 ${isLast ? "" : "pb-3"}`}>
      <div className="flex flex-col items-center w-4 shrink-0">
        <div
          className="w-2 h-2 rounded-full shrink-0 mt-0.5"
          style={{ background: dotColor }}
        />
        {!isLast && <div className="w-px flex-1 bg-border mt-1" />}
      </div>
      <div className="flex-1">
        <div className="text-xs text-text-primary mb-0.5">{event.event}</div>
        <div className="text-[10px] font-mono text-text-muted">{event.date}</div>
      </div>
    </div>
  )
}
