interface Props {
  tick: number;
}

interface TaskCard {
  id: number;
  title: string;
  priority: "critical" | "high" | "medium" | "low";
  assignee: string;
}

const priorityColors: Record<TaskCard["priority"], string> = {
  critical: "#ef4444",
  high: "#f59e0b",
  medium: "#38bdf8",
  low: "#94a3b8",
};

const columns: { name: string; wip?: number; tasks: TaskCard[] }[] = [
  {
    name: "Backlog",
    tasks: [
      { id: 5, title: "Write API docs", priority: "low", assignee: "E2" },
      { id: 6, title: "Perf benchmarks", priority: "medium", assignee: "QA" },
    ],
  },
  {
    name: "In Progress",
    wip: 3,
    tasks: [
      { id: 3, title: "Build auth module", priority: "high", assignee: "E1" },
      { id: 4, title: "Design landing page", priority: "medium", assignee: "UX" },
    ],
  },
  {
    name: "In Review",
    tasks: [{ id: 2, title: "Setup CI pipeline", priority: "high", assignee: "CTO" }],
  },
  {
    name: "Done",
    tasks: [
      { id: 1, title: "Init project", priority: "medium", assignee: "CTO" },
      { id: 7, title: "Add logging", priority: "low", assignee: "E1" },
      { id: 8, title: "Schema validation", priority: "high", assignee: "E2" },
    ],
  },
];

function MiniCard({ task, highlight }: { task: TaskCard; highlight: boolean }) {
  return (
    <div
      className="rounded-md p-2 border transition-all duration-500"
      style={{
        background: highlight ? "var(--dp-bg-card-hover)" : "var(--dp-bg-card)",
        borderColor: highlight ? "var(--dp-accent)" : "var(--dp-border)",
      }}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ background: priorityColors[task.priority] }}
        />
        <span className="text-[9px] truncate" style={{ color: "var(--dp-text-primary)" }}>
          {task.title}
        </span>
      </div>
      <div className="flex items-center gap-1">
        <span
          className="w-3.5 h-3.5 rounded-full text-[6px] flex items-center justify-center font-bold"
          style={{ background: "var(--dp-border-bright)", color: "var(--dp-text-secondary)" }}
        >
          {task.assignee[0]}
        </span>
        <span className="text-[7px]" style={{ color: "var(--dp-text-muted)" }}>
          {task.assignee}
        </span>
      </div>
    </div>
  );
}

export default function TaskBoardMini({ tick }: Props) {
  // Highlight a card that's "moving" every few ticks
  const highlightId = tick % 6 < 3 ? 3 : 2;

  return (
    <div className="w-full">
      <div className="grid grid-cols-4 gap-2 px-1">
        {columns.map((col) => (
          <div key={col.name}>
            <div className="flex items-center justify-between mb-2 px-1">
              <span className="text-[9px] font-semibold" style={{ color: "var(--dp-text-secondary)" }}>
                {col.name}
              </span>
              <span className="flex items-center gap-1">
                <span
                  className="text-[8px] px-1 rounded"
                  style={{ background: "var(--dp-border)", color: "var(--dp-text-muted)" }}
                >
                  {col.tasks.length}
                </span>
                {col.wip && (
                  <span
                    className="text-[7px] px-1 rounded"
                    style={{ background: "rgba(245, 158, 11, 0.15)", color: "var(--dp-warning)" }}
                  >
                    WIP {col.wip}
                  </span>
                )}
              </span>
            </div>
            <div className="space-y-1.5">
              {col.tasks.map((task) => (
                <MiniCard key={task.id} task={task} highlight={task.id === highlightId} />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 text-center">
        <span
          className="text-[9px] px-2 py-0.5 rounded-full border inline-block"
          style={{ color: "var(--dp-accent)", borderColor: "var(--dp-border-bright)", background: "var(--dp-bg-surface)" }}
        >
          Kanban, Agile sprints, or sequential pipelines
        </span>
      </div>
    </div>
  );
}
