import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import MiniOrgGraph from '../components/MiniOrgGraph';
import {
  activityFeed,
  companyStats,
  departments,
  agents,
  formatRelativeTime,
  getGreeting,
  departmentColors,
} from '../data/mockData';

function AgentDots({ departmentId, count }: { departmentId: string; count: number }) {
  const deptAgents = agents.filter((a) => a.department === departmentId);
  const color = departmentColors[departmentId] || '#6366f1';

  return (
    <span style={{ display: 'inline-flex', gap: '3px', alignItems: 'center' }}>
      {deptAgents.slice(0, count).map((agent) => (
        <span
          key={agent.id}
          title={`${agent.name} — ${agent.status}`}
          style={{
            display: 'inline-block',
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: agent.status !== 'idle' ? color : 'transparent',
            border: agent.status === 'idle' ? `1.5px solid ${color}` : 'none',
            opacity: agent.status === 'idle' ? 0.4 : 0.9,
          }}
        />
      ))}
    </span>
  );
}

export default function Dashboard() {
  const greeting = getGreeting();
  const budgetPct = Math.round((companyStats.spentToday / companyStats.dailyBudget) * 100);
  const daysAtRate = companyStats.dailyBudget / companyStats.spentToday;

  return (
    <Layout>
      <div
        style={{
          maxWidth: '1200px',
          margin: '0 auto',
          padding: '40px 32px 64px',
        }}
      >
        {/* Greeting */}
        <div style={{ marginBottom: '40px' }}>
          <h1
            style={{
              fontSize: '24px',
              fontWeight: 600,
              color: 'rgba(255,255,255,0.92)',
              margin: '0 0 8px 0',
              letterSpacing: '-0.02em',
              lineHeight: 1.3,
            }}
          >
            {greeting}. Your organization is operating normally.
          </h1>
          <p
            style={{
              fontSize: '15px',
              color: 'rgba(255,255,255,0.45)',
              fontWeight: 400,
              margin: 0,
              lineHeight: 1.6,
            }}
          >
            {companyStats.activeAgents} of {companyStats.totalAgents} people active.{' '}
            {companyStats.tasksInProgress} tasks in progress.{' '}
            <span style={{ color: 'rgba(255,255,255,0.6)' }}>${companyStats.spentToday}</span>{' '}
            spent today.
          </p>
        </div>

        {/* Two-column layout */}
        <div style={{ display: 'flex', gap: '48px', alignItems: 'flex-start' }}>
          {/* Left column — 55% */}
          <div style={{ flex: '0 0 55%', minWidth: 0 }}>
            {/* Activity feed */}
            <section>
              <p
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'rgba(255,255,255,0.3)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  margin: '0 0 20px 0',
                }}
              >
                What's happening
              </p>

              <div>
                {activityFeed.map((event, idx) => (
                  <div
                    key={event.id}
                    style={{
                      paddingBottom: idx < activityFeed.length - 1 ? '16px' : 0,
                      marginBottom: idx < activityFeed.length - 1 ? '16px' : 0,
                      borderBottom: idx < activityFeed.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
                    }}
                  >
                    <p
                      style={{
                        fontSize: '14px',
                        lineHeight: 1.5,
                        margin: 0,
                        color: 'rgba(255,255,255,0.65)',
                        fontWeight: 400,
                      }}
                    >
                      <Link
                        to="/db/agent"
                        style={{
                          fontWeight: 600,
                          color: 'rgba(255,255,255,0.88)',
                          textDecoration: 'none',
                        }}
                      >
                        {event.fromAgent}
                      </Link>{' '}
                      {event.action}{' '}
                      {event.toAgent && (
                        <Link
                          to="/db/agent"
                          style={{
                            fontWeight: 600,
                            color: 'rgba(255,255,255,0.88)',
                            textDecoration: 'none',
                          }}
                        >
                          {event.toAgent}
                        </Link>
                      )}
                      {event.subject && (
                        <span style={{ fontWeight: 500, color: 'rgba(255,255,255,0.75)' }}>
                          {event.subject}
                        </span>
                      )}
                    </p>
                    <p
                      style={{
                        fontSize: '12px',
                        color: 'rgba(255,255,255,0.3)',
                        margin: '3px 0 0',
                        fontWeight: 400,
                      }}
                    >
                      {formatRelativeTime(event.timestamp)}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {/* Budget */}
            <section style={{ marginTop: '48px' }}>
              <p
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'rgba(255,255,255,0.3)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  margin: '0 0 16px 0',
                }}
              >
                Money
              </p>
              <p
                style={{
                  fontSize: '15px',
                  color: 'rgba(255,255,255,0.75)',
                  fontWeight: 400,
                  margin: '0 0 10px 0',
                }}
              >
                <span style={{ fontWeight: 600, color: 'rgba(255,255,255,0.9)', fontSize: '16px' }}>
                  ${companyStats.spentToday}
                </span>{' '}
                of ${companyStats.dailyBudget} spent today ({budgetPct}%)
              </p>
              {/* Progress bar */}
              <div
                style={{
                  height: '3px',
                  backgroundColor: 'rgba(255,255,255,0.08)',
                  borderRadius: '2px',
                  overflow: 'hidden',
                  marginBottom: '10px',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${budgetPct}%`,
                    backgroundColor: '#10b981',
                    borderRadius: '2px',
                    transition: 'width 400ms ease',
                  }}
                />
              </div>
              <p
                style={{
                  fontSize: '13px',
                  color: 'rgba(255,255,255,0.35)',
                  margin: 0,
                  fontWeight: 400,
                }}
              >
                ≈ {daysAtRate.toFixed(1)} days at this rate before budget is reached
              </p>
            </section>
          </div>

          {/* Right column — 45% */}
          <div style={{ flex: '0 0 calc(45% - 48px)', minWidth: 0 }}>
            {/* Mini org graph */}
            <section style={{ marginBottom: '40px' }}>
              <MiniOrgGraph />
            </section>

            {/* Departments */}
            <section>
              <p
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'rgba(255,255,255,0.3)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  margin: '0 0 16px 0',
                }}
              >
                Departments
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {departments.map((dept) => {
                  const deptAgents = agents.filter((a) => a.department === dept.id);
                  const activeCount = deptAgents.filter((a) => a.status !== 'idle').length;

                  return (
                    <div
                      key={dept.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span
                          style={{
                            fontSize: '14px',
                            fontWeight: 500,
                            color: 'rgba(255,255,255,0.8)',
                            minWidth: '90px',
                          }}
                        >
                          {dept.name}
                        </span>
                        <AgentDots
                          departmentId={dept.id}
                          count={deptAgents.length}
                        />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span
                          style={{
                            fontSize: '12px',
                            color: 'rgba(255,255,255,0.3)',
                          }}
                        >
                          {activeCount}/{deptAgents.length} active
                        </span>
                        <span
                          style={{
                            fontSize: '13px',
                            fontWeight: 500,
                            color: 'rgba(255,255,255,0.55)',
                          }}
                        >
                          ${dept.spentToday}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>
        </div>
      </div>
    </Layout>
  );
}
