import { useNavigate } from 'react-router-dom';
import { agents, departmentColors } from '../data/mockData';

interface NodePosition {
  id: string;
  x: number;
  y: number;
  name: string;
  status: string;
  department: string;
  reportsTo: string | null;
}

const WIDTH = 320;
const HEIGHT = 220;

function buildLayout(): NodePosition[] {
  // Manually layout for a clean tree look
  const nodes: NodePosition[] = [
    // CEO — row 1
    { id: 'alexandra-chen', x: 160, y: 28, name: 'Alexandra Chen', status: 'active', department: 'executive', reportsTo: null },
    // VPs — row 2
    { id: 'james-park', x: 65, y: 82, name: 'James Park', status: 'active', department: 'engineering', reportsTo: 'alexandra-chen' },
    { id: 'sarah-kim', x: 160, y: 82, name: 'Sarah Kim', status: 'active', department: 'marketing', reportsTo: 'alexandra-chen' },
    { id: 'michael-torres', x: 245, y: 82, name: 'Michael Torres', status: 'active', department: 'finance', reportsTo: 'alexandra-chen' },
    // Engineering ICs — row 3
    { id: 'maria-santos', x: 22, y: 148, name: 'Maria Santos', status: 'working', department: 'engineering', reportsTo: 'james-park' },
    { id: 'kai-nakamura', x: 70, y: 148, name: 'Kai Nakamura', status: 'active', department: 'engineering', reportsTo: 'james-park' },
    { id: 'priya-patel', x: 105, y: 148, name: 'Priya Patel', status: 'idle', department: 'engineering', reportsTo: 'james-park' },
    // Marketing ICs — row 3
    { id: 'elena-vasquez', x: 150, y: 148, name: 'Elena Vasquez', status: 'active', department: 'marketing', reportsTo: 'sarah-kim' },
    { id: 'felix-morgan', x: 188, y: 148, name: 'Felix Morgan', status: 'idle', department: 'marketing', reportsTo: 'sarah-kim' },
    // Finance IC — row 3
    { id: 'michael-f', x: 240, y: 148, name: 'CFO Asst.', status: 'active', department: 'finance', reportsTo: 'michael-torres' },
    // HR — row 3
    { id: 'lisa-wang', x: 282, y: 148, name: 'Lisa Wang', status: 'active', department: 'hr', reportsTo: 'alexandra-chen' },
    // HR IC — row 4
    { id: 'david-brown', x: 296, y: 196, name: 'David Brown', status: 'idle', department: 'hr', reportsTo: 'lisa-wang' },
  ];
  return nodes;
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'active': return '#10b981';
    case 'working': return '#6366f1';
    case 'idle': return 'transparent';
    default: return 'transparent';
  }
}

function getStatusStroke(status: string, dept: string): string {
  if (status === 'idle') return departmentColors[dept] || '#6b7280';
  return 'transparent';
}

export default function MiniOrgGraph() {
  const navigate = useNavigate();
  const nodes = buildLayout();
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  const lines: { x1: number; y1: number; x2: number; y2: number; key: string }[] = [];
  for (const node of nodes) {
    if (node.reportsTo) {
      const parent = nodeMap.get(node.reportsTo);
      if (parent) {
        lines.push({ x1: parent.x, y1: parent.y, x2: node.x, y2: node.y, key: `${node.reportsTo}-${node.id}` });
      }
    }
  }

  const agentMap = new Map(agents.map((a) => [a.id, a]));

  return (
    <div>
      <p
        style={{
          fontSize: '11px',
          fontWeight: 600,
          color: 'rgba(255,255,255,0.3)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          marginBottom: '12px',
          margin: '0 0 12px 0',
        }}
      >
        Live Pulse
      </p>
      <svg
        width={WIDTH}
        height={HEIGHT}
        style={{ display: 'block', overflow: 'visible' }}
        aria-label="Organization structure graph"
      >
        {/* Connection lines */}
        {lines.map((l) => (
          <line
            key={l.key}
            x1={l.x1}
            y1={l.y1}
            x2={l.x2}
            y2={l.y2}
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="1"
          />
        ))}

        {/* Agent nodes */}
        {nodes.map((node) => {
          const agent = agentMap.get(node.id);
          const fillColor = getStatusColor(node.status);
          const strokeColor = getStatusStroke(node.status, node.department);
          const deptColor = departmentColors[node.department] || '#6b7280';
          const isIdle = node.status === 'idle';
          const r = node.reportsTo === null ? 9 : 6;

          return (
            <g
              key={node.id}
              style={{ cursor: agent ? 'pointer' : 'default' }}
              onClick={() => {
                if (agent) navigate('/db/agent');
              }}
            >
              <circle
                cx={node.x}
                cy={node.y}
                r={r + 4}
                fill="transparent"
              />
              <circle
                cx={node.x}
                cy={node.y}
                r={r}
                fill={isIdle ? '#0f1117' : fillColor}
                stroke={isIdle ? deptColor : deptColor}
                strokeWidth={isIdle ? 1.5 : 0}
                opacity={isIdle ? 0.5 : 1}
              />
              {/* Working indicator — small inner dot */}
              {node.status === 'working' && (
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={2.5}
                  fill="white"
                  opacity={0.8}
                />
              )}
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div
        style={{
          display: 'flex',
          gap: '16px',
          marginTop: '12px',
        }}
      >
        {[
          { label: 'Active', color: '#10b981', filled: true },
          { label: 'Working', color: '#6366f1', filled: true },
          { label: 'Idle', color: 'rgba(255,255,255,0.2)', filled: false },
        ].map((item) => (
          <div
            key={item.label}
            style={{ display: 'flex', alignItems: 'center', gap: '5px' }}
          >
            <div
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: item.filled ? item.color : 'transparent',
                border: item.filled ? 'none' : `1.5px solid ${item.color}`,
              }}
            />
            <span
              style={{ fontSize: '11px', color: 'rgba(255,255,255,0.35)', fontWeight: 400 }}
            >
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
