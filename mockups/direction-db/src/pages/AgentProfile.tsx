import Layout from '../components/Layout';
import { agents, getAgentById } from '../data/mockData';

// Default to Maria Santos as the profile subject
const PROFILE_ID = 'maria-santos';

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string }> = {
    active: { label: 'Active', color: '#10b981' },
    working: { label: 'Working', color: '#6366f1' },
    idle: { label: 'Idle', color: 'rgba(255,255,255,0.35)' },
    completed: { label: 'Completed', color: '#10b981' },
    in_progress: { label: 'In progress', color: '#6366f1' },
    failed: { label: 'Failed', color: '#f43f5e' },
  };
  const s = map[status] || { label: status, color: 'rgba(255,255,255,0.4)' };
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        fontSize: '12px',
        color: s.color,
        fontWeight: 500,
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: s.color,
          display: 'inline-block',
        }}
      />
      {s.label}
    </span>
  );
}

interface TimelineEvent {
  label: string;
  date: string;
}

function CareerTimeline({ events }: { events: TimelineEvent[] }) {
  return (
    <div
      style={{
        position: 'relative',
        paddingTop: '24px',
        paddingBottom: '8px',
      }}
    >
      {/* Horizontal baseline */}
      <div
        style={{
          position: 'absolute',
          top: '32px',
          left: '8px',
          right: '8px',
          height: '1px',
          backgroundColor: 'rgba(255,255,255,0.08)',
        }}
      />

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          position: 'relative',
        }}
      >
        {events.map((evt, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px',
              flex: 1,
              padding: '0 4px',
            }}
          >
            {/* Dot on the line */}
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: idx === events.length - 1 ? '#6366f1' : 'rgba(255,255,255,0.25)',
                flexShrink: 0,
                zIndex: 1,
              }}
            />

            {/* Label below */}
            <p
              style={{
                fontSize: '11px',
                color: 'rgba(255,255,255,0.4)',
                margin: 0,
                textAlign: 'center',
                lineHeight: 1.4,
                fontWeight: 400,
              }}
            >
              {evt.label}
            </p>
            <p
              style={{
                fontSize: '11px',
                color: 'rgba(255,255,255,0.2)',
                margin: 0,
                textAlign: 'center',
                fontWeight: 400,
              }}
            >
              {evt.date}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AgentProfile() {
  const agent = getAgentById(PROFILE_ID);

  if (!agent) {
    return (
      <Layout>
        <div style={{ padding: '40px 32px', color: 'rgba(255,255,255,0.5)' }}>
          Agent not found.
        </div>
      </Layout>
    );
  }

  const connectionAgents = agent.connections
    .map((c) => {
      const a = agents.find((ag) => ag.id === c.agentId);
      return a ? { ...a, messages: c.messages } : null;
    })
    .filter(Boolean) as (typeof agents[number] & { messages: number })[];

  const timelineEvents: TimelineEvent[] = [
    { label: 'Hired', date: agent.hiredDate },
    { label: 'First task', date: agent.firstTaskDate },
    ...(agent.promotedDate ? [{ label: 'Promoted to Senior', date: agent.promotedDate }] : []),
    { label: `${agent.tasksCompleted} tasks completed`, date: 'Today' },
  ];

  const workItems = agent.recentWork.slice(0, 7);

  return (
    <Layout>
      <div
        style={{
          maxWidth: '680px',
          margin: '0 auto',
          padding: '40px 32px 80px',
        }}
      >
        {/* Name & status */}
        <div style={{ marginBottom: '40px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '6px' }}>
            <h1
              style={{
                fontSize: '28px',
                fontWeight: 600,
                color: 'rgba(255,255,255,0.95)',
                margin: 0,
                letterSpacing: '-0.02em',
                lineHeight: 1.2,
              }}
            >
              {agent.name}
            </h1>
            <StatusBadge status={agent.status} />
          </div>

          <p
            style={{
              fontSize: '14px',
              color: 'rgba(255,255,255,0.4)',
              margin: '0 0 12px 0',
              fontWeight: 400,
            }}
          >
            {agent.role} · {agent.department.charAt(0).toUpperCase() + agent.department.slice(1)}
          </p>

          {agent.currentTask && (
            <p
              style={{
                fontSize: '14px',
                color: '#6366f1',
                margin: 0,
                fontWeight: 500,
              }}
            >
              Currently working on {agent.currentTask}
            </p>
          )}
        </div>

        {/* Career summary timeline */}
        <section style={{ marginBottom: '44px' }}>
          <p
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: 'rgba(255,255,255,0.25)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              margin: '0 0 4px 0',
            }}
          >
            Career
          </p>
          <CareerTimeline events={timelineEvents} />
        </section>

        {/* Performance prose */}
        <section style={{ marginBottom: '44px' }}>
          <p
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: 'rgba(255,255,255,0.25)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              margin: '0 0 14px 0',
            }}
          >
            Performance
          </p>
          <p
            style={{
              fontSize: '15px',
              color: 'rgba(255,255,255,0.65)',
              lineHeight: 1.7,
              margin: 0,
              fontWeight: 400,
            }}
          >
            {agent.name.split(' ')[0]} has completed{' '}
            <span style={{ fontWeight: 600, color: 'rgba(255,255,255,0.85)' }}>
              {agent.tasksCompleted} tasks
            </span>{' '}
            with a{' '}
            <span style={{ fontWeight: 600, color: '#10b981' }}>
              {agent.successRate}% success rate
            </span>
            , averaging{' '}
            <span style={{ fontWeight: 500, color: 'rgba(255,255,255,0.75)' }}>
              {agent.avgHoursPerTask}h per task
            </span>{' '}
            at{' '}
            <span style={{ fontWeight: 500, color: 'rgba(255,255,255,0.75)' }}>
              ${agent.avgCostPerTask} each
            </span>
            . She is one of the most efficient people in{' '}
            {agent.department.charAt(0).toUpperCase() + agent.department.slice(1)}.
          </p>

          {/* Mini stats row */}
          <div
            style={{
              display: 'flex',
              gap: '32px',
              marginTop: '20px',
            }}
          >
            {[
              { label: 'Tasks', value: agent.tasksCompleted.toString() },
              { label: 'Success rate', value: `${agent.successRate}%` },
              { label: 'Avg duration', value: `${agent.avgHoursPerTask}h` },
              { label: 'Avg cost', value: `$${agent.avgCostPerTask}` },
            ].map((stat) => (
              <div key={stat.label}>
                <p
                  style={{
                    fontSize: '19px',
                    fontWeight: 600,
                    color: 'rgba(255,255,255,0.88)',
                    margin: '0 0 2px 0',
                    letterSpacing: '-0.01em',
                  }}
                >
                  {stat.value}
                </p>
                <p
                  style={{
                    fontSize: '11px',
                    color: 'rgba(255,255,255,0.3)',
                    margin: 0,
                    fontWeight: 400,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                  }}
                >
                  {stat.label}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Recent work */}
        <section style={{ marginBottom: '44px' }}>
          <p
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: 'rgba(255,255,255,0.25)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              margin: '0 0 16px 0',
            }}
          >
            Recent work
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
            {workItems.map((task, idx) => (
              <div
                key={idx}
                style={{
                  padding: '14px 0',
                  borderBottom: idx < workItems.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p
                      style={{
                        fontSize: '14px',
                        fontWeight: 600,
                        color: 'rgba(255,255,255,0.85)',
                        margin: '0 0 3px 0',
                        letterSpacing: '-0.005em',
                      }}
                    >
                      {task.title}
                    </p>
                    <p
                      style={{
                        fontSize: '13px',
                        color: 'rgba(255,255,255,0.4)',
                        margin: '0 0 6px 0',
                        fontWeight: 400,
                        lineHeight: 1.4,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {task.description}
                    </p>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                      <StatusBadge status={task.status} />
                      <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.25)', fontWeight: 400 }}>
                        {task.duration}h · ${task.cost.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Connections */}
        <section style={{ marginBottom: '44px' }}>
          <p
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: 'rgba(255,255,255,0.25)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              margin: '0 0 14px 0',
            }}
          >
            Connections
          </p>
          <p
            style={{
              fontSize: '14px',
              color: 'rgba(255,255,255,0.55)',
              margin: 0,
              lineHeight: 1.7,
              fontWeight: 400,
            }}
          >
            Works most closely with:{' '}
            {connectionAgents.map((ca, idx) => (
              <span key={ca.id}>
                <span
                  style={{
                    fontWeight: 500,
                    color: 'rgba(255,255,255,0.8)',
                  }}
                >
                  {ca.name}
                </span>
                <span style={{ color: 'rgba(255,255,255,0.3)' }}>
                  {' '}({ca.messages} messages)
                </span>
                {idx < connectionAgents.length - 1 && (
                  <span style={{ color: 'rgba(255,255,255,0.2)' }}>, </span>
                )}
              </span>
            ))}
          </p>
        </section>

        {/* Tools */}
        <section>
          <p
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: 'rgba(255,255,255,0.25)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              margin: '0 0 12px 0',
            }}
          >
            Tools
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {agent.tools.map((tool) => (
              <span
                key={tool}
                style={{
                  display: 'inline-block',
                  padding: '4px 10px',
                  backgroundColor: 'rgba(255,255,255,0.05)',
                  borderRadius: '4px',
                  fontSize: '12px',
                  color: 'rgba(255,255,255,0.5)',
                  fontWeight: 400,
                  fontFamily: 'ui-monospace, monospace',
                  letterSpacing: '0.01em',
                }}
              >
                {tool}
              </span>
            ))}
          </div>
        </section>
      </div>
    </Layout>
  );
}
