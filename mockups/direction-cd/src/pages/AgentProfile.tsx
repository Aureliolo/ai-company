import { Layout } from '../components/Layout';
import { agentProfile } from '../data/mockData';

const taskTypeColors: Record<string, string> = {
  research: '#60a5fa',
  analysis: '#a78bfa',
  report: '#34d399',
};

const taskTypeLabels: Record<string, string> = {
  research: 'Research',
  analysis: 'Analysis',
  report: 'Report',
};

const activityTypeColors: Record<string, string> = {
  complete: '#22d3ee',
  receive: '#60a5fa',
  tool: '#6b7280',
  start: '#22c55e',
  submit: '#a78bfa',
  flag: '#f59e0b',
};

export function AgentProfile() {
  const agent = agentProfile;
  const maxEnd = Math.max(...agent.taskHistory.map((t) => t.start + t.duration));

  return (
    <Layout>
      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Page header */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 2 }}>
            <h1 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
              {agent.shortName}
            </h1>
            <span
              style={{
                fontSize: 11,
                color: 'var(--text-dim)',
                fontFamily: 'var(--font-mono)',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid var(--border)',
                padding: '2px 8px',
                borderRadius: 4,
              }}
            >
              {agent.role}
            </span>
            <span
              className="status-pulse"
              style={{
                display: 'inline-block',
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: '#22d3ee',
                marginLeft: 2,
              }}
            />
            <span style={{ fontSize: 11, color: '#22d3ee', fontFamily: 'var(--font-mono)' }}>Active</span>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            {agent.name} · {agent.department} · {agent.autonomyLevel}
          </p>
        </div>

        {/* Two-column layout */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 3fr', gap: 20, alignItems: 'start' }}>

          {/* LEFT COLUMN */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            {/* Identity card */}
            <SectionCard title="Identity">
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
                <div
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: '50%',
                    background: 'rgba(34, 211, 238, 0.1)',
                    border: '2px solid rgba(34, 211, 238, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 18,
                    fontWeight: 700,
                    color: 'var(--accent)',
                    fontFamily: 'var(--font-mono)',
                    flexShrink: 0,
                  }}
                >
                  MS
                </div>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 3 }}>
                    {agent.name}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>{agent.role}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>{agent.department} · {agent.level}</div>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <IdentRow label="Status" value={<StatusBadge />} />
                <IdentRow label="Autonomy" value={<AutonomyBadge level={agent.autonomyLevel} />} />
                <IdentRow label="Department" value={agent.department} />
                <IdentRow label="Level" value={agent.level} />
              </div>
            </SectionCard>

            {/* Performance metrics */}
            <SectionCard title="Performance">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <PerfMetric label="Tasks Completed" value={String(agent.performance.tasksCompleted)} unit="" color="var(--accent)" />
                <PerfMetric label="Avg Time" value={String(agent.performance.avgCompletionTime)} unit="h" color="var(--accent)" />
                <PerfMetric label="Success Rate" value={String(agent.performance.successRate)} unit="%" color="#22c55e" />
                <PerfMetric label="Cost / Task" value={`$${agent.performance.costEfficiency}`} unit="" color="var(--amber)" />
              </div>
            </SectionCard>

            {/* Tools */}
            <SectionCard title="Available Tools">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {agent.tools.map((tool) => (
                  <span
                    key={tool}
                    style={{
                      fontSize: 11,
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--accent)',
                      background: 'rgba(34, 211, 238, 0.08)',
                      border: '1px solid rgba(34, 211, 238, 0.2)',
                      padding: '4px 8px',
                      borderRadius: 4,
                    }}
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </SectionCard>

            {/* Career timeline */}
            <SectionCard title="Career Timeline">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {[
                  { date: 'Mar 1, 2026', event: 'Hired as Market Analyst', type: 'hire' },
                  { date: 'Mar 15, 2026', event: 'Promoted to Senior', type: 'promote' },
                  { date: 'Mar 23, 2026', event: '47 tasks completed — milestone', type: 'milestone' },
                ].map((item, i, arr) => (
                  <div key={i} style={{ display: 'flex', gap: 10, paddingBottom: i < arr.length - 1 ? 12 : 0 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 16, flexShrink: 0 }}>
                      <div
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: item.type === 'hire' ? '#22c55e' : item.type === 'promote' ? 'var(--accent)' : 'var(--amber)',
                          flexShrink: 0,
                          marginTop: 2,
                        }}
                      />
                      {i < arr.length - 1 && (
                        <div style={{ width: 1, flex: 1, background: 'var(--border)', marginTop: 4 }} />
                      )}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, color: 'var(--text-primary)', marginBottom: 1 }}>{item.event}</div>
                      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>{item.date}</div>
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>

          </div>

          {/* RIGHT COLUMN */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            {/* Task Timeline */}
            <SectionCard title="Task Timeline">
              {/* Legend */}
              <div style={{ display: 'flex', gap: 14, marginBottom: 14, fontSize: 10, color: 'var(--text-dim)', flexWrap: 'wrap' }}>
                {Object.entries(taskTypeColors).map(([type, color]) => (
                  <span key={type} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }} />
                    {taskTypeLabels[type]}
                  </span>
                ))}
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: 'var(--amber)', flexShrink: 0 }} />
                  In Progress
                </span>
                <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)' }}>Last {agent.taskHistory.length} tasks</span>
              </div>

              {/* Gantt bars */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {agent.taskHistory.map((task) => {
                  const leftPct = (task.start / maxEnd) * 100;
                  const widthPct = Math.max((task.duration / maxEnd) * 100, 1.5);
                  const color = task.completed ? taskTypeColors[task.type] : 'var(--amber)';

                  return (
                    <div key={task.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div
                        style={{
                          width: 88,
                          fontSize: 10,
                          color: 'var(--text-dim)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          flexShrink: 0,
                          textAlign: 'right',
                        }}
                      >
                        {task.name.length > 14 ? task.name.slice(0, 14) + '…' : task.name}
                      </div>
                      <div style={{ flex: 1, position: 'relative', height: 20, background: 'rgba(255,255,255,0.02)', borderRadius: 3 }}>
                        <div
                          className={!task.completed ? 'task-current' : ''}
                          style={{
                            position: 'absolute',
                            left: `${leftPct}%`,
                            width: `${widthPct}%`,
                            height: '100%',
                            background: color,
                            opacity: task.completed ? 0.65 : 1,
                            borderRadius: 3,
                            boxShadow: !task.completed ? `0 0 8px ${color === 'var(--amber)' ? '#f59e0b' : color}60` : undefined,
                            display: 'flex',
                            alignItems: 'center',
                            overflow: 'hidden',
                          }}
                        >
                          <span style={{ fontSize: 9, color: 'rgba(0,0,0,0.65)', fontWeight: 600, paddingLeft: 4, whiteSpace: 'nowrap' }}>
                            {task.duration}h
                          </span>
                        </div>
                      </div>
                      <span
                        style={{
                          fontSize: 10,
                          width: 16,
                          textAlign: 'center',
                          fontFamily: 'var(--font-mono)',
                          color: task.completed ? 'var(--text-dim)' : 'var(--amber)',
                          flexShrink: 0,
                        }}
                      >
                        {task.completed ? '✓' : '▶'}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Time axis */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginTop: 8,
                  paddingLeft: 96,
                  paddingRight: 24,
                  fontSize: 9,
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-dim)',
                }}
              >
                {Array.from({ length: 6 }, (_, i) => (
                  <span key={i}>{((maxEnd / 5) * i).toFixed(0)}h</span>
                ))}
              </div>
            </SectionCard>

            {/* Recent Activity Log */}
            <SectionCard title="Recent Activity">
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {agent.recentActivity.map((item, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      padding: '7px 0',
                      borderBottom: i < agent.recentActivity.length - 1 ? '1px solid rgba(30,30,46,0.5)' : 'none',
                    }}
                  >
                    <div
                      style={{
                        width: 20,
                        height: 20,
                        borderRadius: 4,
                        background: `${activityTypeColors[item.type] ?? '#475569'}18`,
                        border: `1px solid ${activityTypeColors[item.type] ?? '#475569'}30`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 9,
                        color: activityTypeColors[item.type] ?? '#475569',
                        flexShrink: 0,
                        fontFamily: 'var(--font-mono)',
                        marginTop: 1,
                      }}
                    >
                      {item.icon}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 12,
                          color: 'var(--text-secondary)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {item.description}
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--text-dim)',
                        flexShrink: 0,
                        paddingTop: 2,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {item.time}
                    </span>
                  </div>
                ))}
              </div>
            </SectionCard>

          </div>
        </div>
      </div>
    </Layout>
  );
}

// --- Shared sub-components ---

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '10px 16px',
          borderBottom: '1px solid var(--border)',
          fontSize: 11,
          fontWeight: 600,
          color: 'var(--text-secondary)',
          textTransform: 'uppercase',
          letterSpacing: '0.07em',
        }}
      >
        {title}
      </div>
      <div style={{ padding: '14px 16px' }}>
        {children}
      </div>
    </div>
  );
}

function IdentRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0' }}>
      <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{label}</span>
      <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{value}</span>
    </div>
  );
}

function StatusBadge() {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#22d3ee', fontFamily: 'var(--font-mono)' }}>
      <span
        className="status-pulse"
        style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#22d3ee' }}
      />
      Active
    </span>
  );
}

function AutonomyBadge({ level }: { level: string }) {
  return (
    <span
      style={{
        fontSize: 11,
        fontFamily: 'var(--font-mono)',
        color: 'var(--amber)',
        background: 'rgba(245, 158, 11, 0.08)',
        border: '1px solid rgba(245, 158, 11, 0.2)',
        padding: '2px 7px',
        borderRadius: 4,
      }}
    >
      {level}
    </span>
  );
}

function PerfMetric({ label, value, unit, color }: { label: string; value: string; unit: string; color: string }) {
  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        padding: '10px 12px',
      }}
    >
      <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)', color, lineHeight: 1 }}>
        {value}
        <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-dim)', marginLeft: 2 }}>{unit}</span>
      </div>
    </div>
  );
}
