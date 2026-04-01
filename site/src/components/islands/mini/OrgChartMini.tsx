interface Props {
  tick: number;
}

const agents = [
  { id: "ceo", name: "Sarah Chen", role: "CEO", seniority: "C-Suite", x: 200, y: 30, color: "#38bdf8" },
  { id: "cto", name: "CTO", role: "tech_lead", seniority: "C-Suite", x: 100, y: 120, color: "#a78bfa" },
  { id: "design", name: "Design Lead", role: "designer", seniority: "Lead", x: 300, y: 120, color: "#2dd4bf" },
  { id: "eng1", name: "Engineer", role: "developer", seniority: "Senior", x: 50, y: 210, color: "#a78bfa" },
  { id: "eng2", name: "Engineer 2", role: "developer", seniority: "Mid", x: 150, y: 210, color: "#a78bfa" },
  { id: "qa", name: "QA", role: "reviewer", seniority: "Senior", x: 260, y: 210, color: "#2dd4bf" },
  { id: "ux", name: "UX", role: "designer", seniority: "Mid", x: 350, y: 210, color: "#2dd4bf" },
];

const edges = [
  { from: "ceo", to: "cto" },
  { from: "ceo", to: "design" },
  { from: "cto", to: "eng1" },
  { from: "cto", to: "eng2" },
  { from: "design", to: "qa" },
  { from: "design", to: "ux" },
];

export default function OrgChartMini({ tick }: Props) {
  const activeIdx = tick % agents.length;

  return (
    <div className="relative w-full">
      <svg viewBox="0 0 400 270" className="w-full" aria-hidden="true">
        {/* Department groups */}
        <rect x="20" y="95" width="180" height="140" rx="8" fill="none" stroke="#a78bfa" strokeOpacity="0.1" strokeWidth="1" />
        <text x="32" y="112" fill="#a78bfa" fontSize="8" fontFamily="var(--dp-font-sans)" opacity="0.5">Engineering</text>
        <rect x="225" y="95" width="160" height="140" rx="8" fill="none" stroke="#2dd4bf" strokeOpacity="0.1" strokeWidth="1" />
        <text x="237" y="112" fill="#2dd4bf" fontSize="8" fontFamily="var(--dp-font-sans)" opacity="0.5">Design & QA</text>

        {/* Edges */}
        {edges.map((e) => {
          const from = agents.find((a) => a.id === e.from)!;
          const to = agents.find((a) => a.id === e.to)!;
          return (
            <line
              key={`${e.from}-${e.to}`}
              x1={from.x}
              y1={from.y + 20}
              x2={to.x}
              y2={to.y - 5}
              stroke="#a78bfa"
              strokeWidth="0.8"
              strokeOpacity="0.2"
              strokeDasharray="3 3"
            />
          );
        })}

        {/* Communication edge */}
        <line x1="150" y1="220" x2="260" y2="220" stroke="#2dd4bf" strokeWidth="1.5" strokeOpacity="0.4" strokeDasharray="4 3">
          <animate attributeName="strokeDashoffset" from="0" to="-14" dur="2s" repeatCount="indefinite" />
        </line>

        {/* Agent nodes */}
        {agents.map((a, i) => {
          const isActive = i === activeIdx;
          return (
            <g key={a.id}>
              <rect
                x={a.x - 40}
                y={a.y - 5}
                width="80"
                height="35"
                rx="6"
                fill="var(--dp-bg-card)"
                stroke={isActive ? "#38bdf8" : a.color}
                strokeWidth={isActive ? "1.5" : "0.8"}
                strokeOpacity={isActive ? "1" : "0.4"}
              />
              {/* Status dot */}
              <circle
                cx={a.x + 32}
                cy={a.y + 5}
                r="3"
                fill={isActive ? "#10b981" : "#94a3b8"}
              />
              <text x={a.x} y={a.y + 11} textAnchor="middle" fill="var(--dp-text-primary)" fontSize="9" fontWeight="600" fontFamily="var(--dp-font-sans)">
                {a.name}
              </text>
              <text x={a.x} y={a.y + 22} textAnchor="middle" fill="var(--dp-text-secondary)" fontSize="7" fontFamily="var(--dp-font-sans)">
                {a.seniority}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="absolute bottom-2 right-3 text-[9px] px-2 py-0.5 rounded-full border" style={{ color: "var(--dp-accent)", borderColor: "var(--dp-border-bright)", background: "var(--dp-bg-surface)" }}>
        8 seniority levels -- Intern to C-Suite
      </div>
    </div>
  );
}
