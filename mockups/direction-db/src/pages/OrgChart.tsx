import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { agents, departmentColors } from '../data/mockData';

function StatusDot({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    active: '#10b981',
    working: '#6366f1',
    idle: 'rgba(255,255,255,0.18)',
  };
  return (
    <span
      style={{
        display: 'inline-block',
        width: '7px',
        height: '7px',
        borderRadius: '50%',
        backgroundColor: status === 'idle' ? 'transparent' : colorMap[status],
        border: status === 'idle' ? '1.5px solid rgba(255,255,255,0.25)' : 'none',
        flexShrink: 0,
        marginTop: '2px',
      }}
      title={status}
    />
  );
}

interface DeptRowProps {
  deptId: string;
  name: string;
  color: string;
}

function DepartmentRow({ deptId, name, color }: DeptRowProps) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  const allAgents = agents.filter((a) => a.department === deptId);
  const activeCount = allAgents.filter((a) => a.status !== 'idle').length;
  const tasksCount = allAgents.filter((a) => a.currentTask).length;
  const spentToday = allAgents.reduce((sum, a) => sum + a.spentToday, 0);

  return (
    <div>
      {/* Department header row */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          padding: '16px 0',
          cursor: 'pointer',
          borderBottom: expanded ? 'none' : '1px solid rgba(255,255,255,0.04)',
        }}
      >
        {/* Expand arrow */}
        <div
          style={{
            width: '16px',
            color: 'rgba(255,255,255,0.3)',
            transition: 'transform 200ms ease',
            transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
            flexShrink: 0,
          }}
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        {/* Color accent bar */}
        <div
          style={{
            width: '3px',
            height: '20px',
            borderRadius: '2px',
            backgroundColor: color,
            flexShrink: 0,
          }}
        />

        <div style={{ flex: 1 }}>
          <span
            style={{
              fontSize: '15px',
              fontWeight: 600,
              color: 'rgba(255,255,255,0.88)',
              letterSpacing: '-0.01em',
            }}
          >
            {name}
          </span>
        </div>

        {/* Stats — only show when collapsed */}
        {!expanded && (
          <div style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.35)' }}>
              {activeCount}/{allAgents.length} active
            </span>
            <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.35)' }}>
              {tasksCount} tasks
            </span>
            <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.5)', fontWeight: 500 }}>
              ${spentToday.toFixed(0)}
            </span>
          </div>
        )}
      </div>

      {/* Expanded: department stats + agent list */}
      {expanded && (
        <div
          style={{
            paddingLeft: '32px',
            marginBottom: '8px',
            borderBottom: '1px solid rgba(255,255,255,0.04)',
            paddingBottom: '16px',
          }}
        >
          {/* Inline department stats */}
          <p
            style={{
              fontSize: '13px',
              color: 'rgba(255,255,255,0.35)',
              margin: '0 0 20px 0',
              fontWeight: 400,
            }}
          >
            {allAgents.length} people · {activeCount} active · {tasksCount} tasks in progress · ${spentToday.toFixed(0)} spent today
          </p>

          {/* Connecting tree line area */}
          <div style={{ position: 'relative' }}>
            {/* Vertical line */}
            <div
              style={{
                position: 'absolute',
                left: '0',
                top: '0',
                bottom: '24px',
                width: '1px',
                backgroundColor: 'rgba(255,255,255,0.07)',
              }}
            />

            {/* Agent rows */}
            {allAgents.map((agent, idx) => {
              const isLast = idx === allAgents.length - 1;
              return (
                <div
                  key={agent.id}
                  style={{ position: 'relative', paddingLeft: '20px', paddingBottom: isLast ? 0 : '16px' }}
                >
                  {/* Horizontal connector */}
                  <div
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: '11px',
                      width: '16px',
                      height: '1px',
                      backgroundColor: 'rgba(255,255,255,0.07)',
                    }}
                  />

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                      cursor: 'pointer',
                    }}
                    onClick={() => navigate('/db/agent')}
                  >
                    <StatusDot status={agent.status} />
                    <div style={{ flex: 1 }}>
                      <p
                        style={{
                          fontSize: '14px',
                          fontWeight: 500,
                          color: 'rgba(255,255,255,0.85)',
                          margin: '0 0 2px 0',
                        }}
                      >
                        {agent.name}
                      </p>
                      <p
                        style={{
                          fontSize: '12px',
                          color: 'rgba(255,255,255,0.35)',
                          margin: 0,
                          fontWeight: 400,
                        }}
                      >
                        {agent.role}
                        {agent.currentTask && (
                          <span style={{ color: 'rgba(255,255,255,0.25)' }}>
                            {' — '}{agent.currentTask}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function OrgChart() {
  const navigate = useNavigate();
  const ceo = agents.find((a) => a.role === 'Chief Executive Officer');

  const deptList = [
    { id: 'engineering', name: 'Engineering', color: departmentColors['engineering'] },
    { id: 'marketing', name: 'Marketing', color: departmentColors['marketing'] },
    { id: 'finance', name: 'Finance', color: departmentColors['finance'] },
    { id: 'hr', name: 'HR', color: departmentColors['hr'] },
  ];

  return (
    <Layout>
      <div
        style={{
          maxWidth: '800px',
          margin: '0 auto',
          padding: '40px 32px 64px',
        }}
      >
        {/* Page heading */}
        <div style={{ marginBottom: '48px' }}>
          <h1
            style={{
              fontSize: '24px',
              fontWeight: 600,
              color: 'rgba(255,255,255,0.92)',
              margin: '0 0 8px 0',
              letterSpacing: '-0.02em',
            }}
          >
            Nexus Dynamics
          </h1>
          <p
            style={{
              fontSize: '14px',
              color: 'rgba(255,255,255,0.4)',
              margin: 0,
              fontWeight: 400,
            }}
          >
            12 people across 4 departments
          </p>
        </div>

        {/* CEO row */}
        {ceo && (
          <div style={{ marginBottom: '40px' }}>
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
              Executive
            </p>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                cursor: 'pointer',
              }}
              onClick={() => navigate('/db/agent')}
            >
              {/* Avatar placeholder */}
              <div
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(99,102,241,0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '14px',
                  fontWeight: 600,
                  color: '#6366f1',
                  flexShrink: 0,
                }}
              >
                {ceo.name.split(' ').map((n) => n[0]).join('')}
              </div>
              <div>
                <p
                  style={{
                    fontSize: '16px',
                    fontWeight: 600,
                    color: 'rgba(255,255,255,0.9)',
                    margin: '0 0 2px 0',
                    letterSpacing: '-0.01em',
                  }}
                >
                  {ceo.name}
                </p>
                <p
                  style={{
                    fontSize: '13px',
                    color: 'rgba(255,255,255,0.4)',
                    margin: 0,
                    fontWeight: 400,
                  }}
                >
                  {ceo.role}
                  {ceo.currentTask && (
                    <span style={{ color: 'rgba(255,255,255,0.25)' }}>
                      {' — '}{ceo.currentTask}
                    </span>
                  )}
                </p>
              </div>
              <div style={{ marginLeft: 'auto' }}>
                <StatusDot status={ceo.status} />
              </div>
            </div>

            {/* Tree connector to departments */}
            <div
              style={{
                marginLeft: '20px',
                marginTop: '12px',
                height: '32px',
                width: '1px',
                backgroundColor: 'rgba(255,255,255,0.07)',
              }}
            />
          </div>
        )}

        {/* Department section label */}
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
          Departments
        </p>

        {/* Department rows */}
        <div>
          {deptList.map((dept) => (
            <DepartmentRow
              key={dept.id}
              deptId={dept.id}
              name={dept.name}
              color={dept.color}
            />
          ))}
        </div>
      </div>
    </Layout>
  );
}
