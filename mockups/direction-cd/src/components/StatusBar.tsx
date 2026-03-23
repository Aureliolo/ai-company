import { company } from '../data/mockData';

export function StatusBar() {
  return (
    <div
      style={{
        background: '#080810',
        borderBottom: '1px solid #1e1e2e',
        padding: '0 24px',
        height: '32px',
        display: 'flex',
        alignItems: 'center',
        gap: '24px',
        flexShrink: 0,
        fontSize: '11px',
        letterSpacing: '0.05em',
        fontFamily: 'var(--font-mono)',
        color: 'var(--text-secondary)',
        userSelect: 'none',
      }}
    >
      <span style={{ color: 'var(--text-dim)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        Nexus Dynamics
      </span>

      <Divider />

      <StatusItem color="var(--accent)">
        <Dot color="var(--accent)" pulse />
        {company.totalAgents} agents
      </StatusItem>

      <StatusItem>
        <Dot color="#22c55e" />
        {company.activeAgents} active
      </StatusItem>

      <StatusItem>
        <Dot color="var(--amber)" pulse />
        {company.tasksRunning} tasks running
      </StatusItem>

      <Divider />

      <StatusItem>
        <span style={{ color: 'var(--text-dim)' }}>spend</span>
        <span style={{ color: 'var(--text-primary)', marginLeft: 6 }}>
          ${company.spentToday.toFixed(2)}
        </span>
        <span style={{ color: 'var(--text-dim)', marginLeft: 4 }}>today</span>
      </StatusItem>

      <StatusItem>
        <span style={{ color: 'var(--text-dim)' }}>budget</span>
        <span
          style={{
            color: company.budgetPercent > 80 ? 'var(--red)' : company.budgetPercent > 60 ? 'var(--amber)' : 'var(--accent)',
            marginLeft: 6,
          }}
        >
          {company.budgetPercent}%
        </span>
        <span style={{ color: 'var(--text-dim)', marginLeft: 4 }}>used</span>
      </StatusItem>

      <div style={{ flex: 1 }} />

      <StatusItem>
        <Dot color="var(--amber)" />
        {company.pendingApprovals} pending approvals
      </StatusItem>

      <Divider />

      <StatusItem>
        <span style={{ color: '#22c55e', marginRight: 4 }}>●</span>
        <span style={{ color: 'var(--text-dim)' }}>all systems nominal</span>
      </StatusItem>
    </div>
  );
}

function Divider() {
  return (
    <span
      style={{
        width: 1,
        height: 12,
        background: 'var(--border)',
        flexShrink: 0,
      }}
    />
  );
}

function Dot({ color, pulse }: { color: string; pulse?: boolean }) {
  return (
    <span
      className={pulse ? 'status-pulse' : ''}
      style={{
        display: 'inline-block',
        width: 5,
        height: 5,
        borderRadius: '50%',
        background: color,
        marginRight: 5,
        flexShrink: 0,
      }}
    />
  );
}

function StatusItem({ children, color }: { children: React.ReactNode; color?: string }) {
  return (
    <span
      style={{
        display: 'flex',
        alignItems: 'center',
        color: color ?? 'var(--text-secondary)',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}
