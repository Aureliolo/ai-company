import { Link } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { orgChart } from '../data/mockData';

type AgentStatus = 'active' | 'warning' | 'idle' | 'offline';

const statusConfig: Record<AgentStatus, { color: string; label: string; pulse: boolean }> = {
  active: { color: '#22d3ee', label: 'Active', pulse: true },
  warning: { color: '#f59e0b', label: 'Warning', pulse: true },
  idle: { color: '#475569', label: 'Idle', pulse: false },
  offline: { color: '#374151', label: 'Offline', pulse: false },
};

const deptColors: Record<string, string> = {
  Engineering: 'rgba(34, 211, 238, 0.05)',
  Marketing: 'rgba(167, 139, 250, 0.05)',
  Finance: 'rgba(34, 197, 94, 0.05)',
  HR: 'rgba(245, 158, 11, 0.05)',
};

const deptBorderColors: Record<string, string> = {
  Engineering: 'rgba(34, 211, 238, 0.12)',
  Marketing: 'rgba(167, 139, 250, 0.12)',
  Finance: 'rgba(34, 197, 94, 0.12)',
  HR: 'rgba(245, 158, 11, 0.12)',
};

const deptAccents: Record<string, string> = {
  Engineering: '#22d3ee',
  Marketing: '#a78bfa',
  Finance: '#22c55e',
  HR: '#f59e0b',
};

export function OrgChart() {
  const vps = orgChart.vps;
  const allReports = orgChart.reports;
  const hrTeam = allReports['hr'];

  return (
    <Layout>
      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
            Org Chart
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
            Nexus Dynamics · 12 agents · {orgChart.vps.reduce((s, vp) => s + vp.tasksActive, 0) + orgChart.ceo.tasksActive} active tasks
          </p>
        </div>

        {/* CEO Row */}
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <CEONode />
        </div>

        {/* Connector line from CEO to VP row */}
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <div style={{ width: 1, height: 20, background: 'var(--border-bright)' }} />
        </div>

        {/* VP Row + their reports */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 16,
            alignItems: 'start',
          }}
        >
          {vps.map((vp) => {
            const reports = allReports[vp.id as keyof typeof allReports] ?? [];
            return (
              <DeptColumn
                key={vp.id}
                vp={vp}
                reports={reports}
                accent={deptAccents[vp.dept] ?? 'var(--accent)'}
                bgColor={deptColors[vp.dept] ?? 'transparent'}
                borderColor={deptBorderColors[vp.dept] ?? 'var(--border)'}
              />
            );
          })}
        </div>

        {/* HR Row (separate, spans below) */}
        <div
          style={{
            background: deptColors['HR'],
            border: `1px solid ${deptBorderColors['HR']}`,
            borderRadius: 10,
            padding: 16,
          }}
        >
          <div style={{ marginBottom: 12 }}>
            <DeptHeader
              label="Human Resources"
              agentCount={hrTeam.length}
              taskCount={1}
              budgetUsed={2.67}
              accent={deptAccents['HR']}
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
            {hrTeam.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
}

// --- CEO Node ---

function CEONode() {
  const ceo = orgChart.ceo;
  const status = statusConfig[ceo.status];

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid rgba(34, 211, 238, 0.25)',
        borderRadius: 10,
        padding: '20px 28px',
        display: 'flex',
        alignItems: 'center',
        gap: 20,
        minWidth: 380,
        boxShadow: '0 0 24px rgba(34, 211, 238, 0.08)',
        position: 'relative',
      }}
    >
      {/* Accent bar */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          width: 3,
          background: 'var(--accent)',
          borderRadius: '10px 0 0 10px',
        }}
      />

      {/* Avatar */}
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: '50%',
          background: 'rgba(34, 211, 238, 0.1)',
          border: '1.5px solid rgba(34, 211, 238, 0.3)',
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
        AC
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
            {ceo.name}
          </span>
          <span
            className={status.pulse ? 'status-pulse' : ''}
            style={{
              display: 'inline-block',
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: status.color,
              flexShrink: 0,
            }}
          />
          <span style={{ fontSize: 10, color: status.color, fontFamily: 'var(--font-mono)' }}>
            {status.label}
          </span>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
          {ceo.role}
        </div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--text-dim)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          <span style={{ color: 'var(--accent)', marginRight: 4 }}>▶</span>
          {ceo.currentTask}
        </div>
      </div>

      <div
        style={{
          textAlign: 'right',
          flexShrink: 0,
        }}
      >
        <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 2 }}>active tasks</div>
        <div
          style={{
            fontSize: 20,
            fontWeight: 700,
            fontFamily: 'var(--font-mono)',
            color: 'var(--accent)',
          }}
        >
          {ceo.tasksActive}
        </div>
      </div>
    </div>
  );
}

// --- Department Column ---

interface VPNode {
  id: string;
  name: string;
  role: string;
  dept: string;
  status: AgentStatus;
  currentTask: string;
  tasksActive: number;
  budgetUsed: number;
}

interface ReportAgent {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  currentTask: string;
}

function DeptColumn({
  vp,
  reports,
  accent,
  bgColor,
  borderColor,
}: {
  vp: VPNode;
  reports: ReportAgent[];
  accent: string;
  bgColor: string;
  borderColor: string;
}) {
  const statusConf = statusConfig[vp.status];
  const initials = vp.name.split(' ').map((n) => n[0]).join('');
  const activeReports = reports.filter((r) => r.status === 'active').length;

  return (
    <div
      style={{
        background: bgColor,
        border: `1px solid ${borderColor}`,
        borderRadius: 10,
        padding: 14,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      {/* Dept header */}
      <DeptHeader
        label={vp.dept}
        agentCount={reports.length + 1}
        taskCount={vp.tasksActive}
        budgetUsed={vp.budgetUsed}
        accent={accent}
      />

      {/* VP card */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: `1px solid ${borderColor}`,
          borderRadius: 8,
          padding: '12px 14px',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 2,
            background: accent,
          }}
        />
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginTop: 4 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: '50%',
              background: `${accent}1a`,
              border: `1.5px solid ${accent}40`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 11,
              fontWeight: 700,
              color: accent,
              fontFamily: 'var(--font-mono)',
              flexShrink: 0,
            }}
          >
            {initials}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                {vp.name}
              </span>
              <span
                className={statusConf.pulse ? 'status-pulse' : ''}
                style={{
                  display: 'inline-block',
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: statusConf.color,
                }}
              />
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 6 }}>
              {vp.role}
            </div>
            <div
              style={{
                fontSize: 11,
                color: 'var(--text-dim)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              <span style={{ color: accent, marginRight: 4, fontSize: 9 }}>▶</span>
              {vp.currentTask}
            </div>
          </div>
        </div>
        <div
          style={{
            display: 'flex',
            gap: 12,
            marginTop: 10,
            paddingTop: 8,
            borderTop: '1px solid var(--border)',
          }}
        >
          <StatPill label="tasks" value={String(vp.tasksActive)} color={accent} />
          <StatPill label="reports" value={String(reports.length)} color="var(--text-dim)" />
          <StatPill label="active" value={String(activeReports)} color="#22c55e" />
        </div>
      </div>

      {/* Report agents */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {reports.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
      </div>
    </div>
  );
}

// --- Dept Header ---

function DeptHeader({
  label,
  agentCount,
  taskCount,
  budgetUsed,
  accent,
}: {
  label: string;
  agentCount: number;
  taskCount: number;
  budgetUsed: number;
  accent: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div
        style={{
          width: 3,
          height: 14,
          borderRadius: 2,
          background: accent,
          flexShrink: 0,
        }}
      />
      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', flex: 1 }}>
        {label}
      </span>
      <div
        style={{
          display: 'flex',
          gap: 8,
          fontSize: 10,
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-dim)',
        }}
      >
        <span>{agentCount}a</span>
        <span>{taskCount}t</span>
        <span style={{ color: accent }}>${budgetUsed.toFixed(2)}</span>
      </div>
    </div>
  );
}

// --- Agent Card ---

function AgentCard({ agent }: { agent: ReportAgent }) {
  const status = statusConfig[agent.status];
  const initials = agent.name.split(' ').map((n) => n[0]).join('');
  const isAnalyst3 = agent.id === 'analyst-3';

  const card = (
    <div
      className="card-hover"
      style={{
        background: isAnalyst3 ? 'rgba(34,211,238,0.04)' : 'var(--bg-surface)',
        border: `1px solid ${isAnalyst3 ? 'rgba(34,211,238,0.2)' : 'var(--border)'}`,
        borderRadius: 7,
        padding: '9px 12px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        textDecoration: 'none',
        cursor: isAnalyst3 ? 'pointer' : 'default',
      }}
    >
      <div
        style={{
          width: 26,
          height: 26,
          borderRadius: '50%',
          background: `${status.color}18`,
          border: `1px solid ${status.color}30`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 9,
          fontWeight: 700,
          color: status.color,
          fontFamily: 'var(--font-mono)',
          flexShrink: 0,
        }}
      >
        {initials}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 2 }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
            {agent.name}
          </span>
          <span
            className={status.pulse ? 'status-pulse' : ''}
            style={{
              display: 'inline-block',
              width: 5,
              height: 5,
              borderRadius: '50%',
              background: status.color,
              flexShrink: 0,
            }}
          />
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 3 }}>
          {agent.role}
        </div>
        <div
          style={{
            fontSize: 10,
            color: agent.status === 'warning' ? 'var(--amber)' : 'var(--text-dim)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {agent.currentTask}
        </div>
      </div>
    </div>
  );

  if (isAnalyst3) {
    return <Link to="/cd/agent" style={{ textDecoration: 'none' }}>{card}</Link>;
  }
  return card;
}

// --- Stat Pill ---

function StatPill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{label}</span>
      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, color }}>{value}</span>
    </div>
  );
}
