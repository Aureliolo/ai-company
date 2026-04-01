import { useState, useEffect } from "react";

interface Props {
  tick: number;
}

const agents = [
  { id: "ceo", name: "Sarah Chen", role: "CEO", seniority: "C-Suite", x: 250, y: 20, color: "#38bdf8" },
  { id: "cto", name: "CTO", role: "tech_lead", seniority: "C-Suite", x: 100, y: 100, color: "#a78bfa" },
  { id: "design", name: "Design Lead", role: "designer", seniority: "Lead", x: 370, y: 100, color: "#2dd4bf" },
  { id: "eng1", name: "Engineer", role: "developer", seniority: "Senior", x: 60, y: 170, color: "#a78bfa" },
  { id: "eng2", name: "Engineer 2", role: "developer", seniority: "Mid", x: 175, y: 170, color: "#a78bfa" },
  { id: "qa", name: "QA", role: "reviewer", seniority: "Senior", x: 310, y: 170, color: "#2dd4bf" },
  { id: "ux", name: "UX", role: "designer", seniority: "Mid", x: 430, y: 170, color: "#2dd4bf" },
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
  const [prefersReduced, setPrefersReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReduced(mq.matches);
    const handler = (e: MediaQueryListEvent) => setPrefersReduced(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return (
    <div className="relative w-full h-full flex items-center justify-center">
      <svg viewBox="0 0 500 230" className="w-full max-h-full" aria-hidden="true">
        {/* Department groups */}
        <rect x="25" y="75" width="220" height="130" rx="8" fill="none" stroke="#a78bfa" strokeOpacity="0.1" strokeWidth="1" />
        <text x="37" y="90" fill="#a78bfa" fontSize="10" fontFamily="var(--dp-font-sans)" opacity="0.5">Engineering</text>
        <rect x="265" y="75" width="210" height="130" rx="8" fill="none" stroke="#2dd4bf" strokeOpacity="0.1" strokeWidth="1" />
        <text x="277" y="90" fill="#2dd4bf" fontSize="10" fontFamily="var(--dp-font-sans)" opacity="0.5">Design & QA</text>

        {/* Edges */}
        {edges.map((e) => {
          const from = agents.find((a) => a.id === e.from);
          const to = agents.find((a) => a.id === e.to);
          if (!from || !to) return null;
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
        <line x1="215" y1="180" x2="270" y2="180" stroke="#2dd4bf" strokeWidth="1.5" strokeOpacity="0.4" strokeDasharray="4 3">
          {!prefersReduced && <animate attributeName="stroke-dashoffset" from="0" to="-14" dur="2s" repeatCount="indefinite" />}
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
              <text x={a.x} y={a.y + 12} textAnchor="middle" fill="var(--dp-text-primary)" fontSize="12" fontWeight="600" fontFamily="var(--dp-font-sans)">
                {a.name}
              </text>
              <text x={a.x} y={a.y + 24} textAnchor="middle" fill="var(--dp-text-secondary)" fontSize="10" fontFamily="var(--dp-font-sans)">
                {a.seniority}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
