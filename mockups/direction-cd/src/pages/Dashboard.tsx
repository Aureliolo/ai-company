import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import { Layout } from '../components/Layout';
import { Sparkline } from '../components/Sparkline';
import { metrics, departments, activityFeed, budgetBurnData } from '../data/mockData';

export function Dashboard() {
  return (
    <Layout>
      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Page header */}
        <div>
          <h1
            style={{
              fontSize: 18,
              fontWeight: 600,
              color: 'var(--text-primary)',
              letterSpacing: '-0.01em',
            }}
          >
            Overview
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
            Mon, Mar 23 2026 · 15:42 UTC
          </p>
        </div>

        {/* Row 1: Metric cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12,
          }}
        >
          <MetricCard
            label="Tasks Today"
            value="24"
            change="+12%"
            changePositive
            trend={metrics.tasks.trend}
            trendColor="var(--accent)"
            unit=""
          />
          <MetricCard
            label="Active Agents"
            value="8"
            sub="of 12"
            trend={metrics.agents.trend}
            trendColor="var(--accent)"
          />
          <MetricCard
            label="Spend Today"
            value="$42.17"
            sub="67% of daily budget"
            trend={metrics.spend.trend}
            trendColor="var(--amber)"
            subColor="var(--amber)"
            progressValue={67}
            progressColor="var(--amber)"
          />
          <MetricCard
            label="Approvals"
            value="3"
            sub="awaiting review"
            trend={metrics.approvals.trend}
            trendColor="var(--red)"
            subColor="var(--red)"
          />
        </div>

        {/* Row 2: Org Health */}
        <Section label="Org Health" sublabel="Department performance · last 24h">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {departments.map((dept) => (
              <DeptHealthBar key={dept.name} dept={dept} />
            ))}
          </div>
        </Section>

        {/* Row 3: Activity + Budget */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Section label="Activity Stream" sublabel="Real-time agent actions">
            <ActivityStream />
          </Section>

          <Section label="Budget Burn" sublabel="Actual vs forecast · $300/mo budget">
            <BudgetBurnChart />
          </Section>
        </div>
      </div>
    </Layout>
  );
}

// --- Metric Card ---

interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  change?: string;
  changePositive?: boolean;
  trend: number[];
  trendColor?: string;
  subColor?: string;
  unit?: string;
  progressValue?: number;
  progressColor?: string;
}

function MetricCard({
  label,
  value,
  sub,
  change,
  changePositive,
  trend,
  trendColor = 'var(--accent)',
  subColor = 'var(--text-dim)',
  progressValue,
  progressColor,
}: MetricCardProps) {
  return (
    <div
      className="card-hover"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
            {label}
          </div>
          <div
            style={{
              fontSize: 26,
              fontWeight: 700,
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              lineHeight: 1,
              letterSpacing: '-0.02em',
            }}
          >
            {value}
          </div>
        </div>
        <Sparkline data={trend} color={trendColor} width={60} height={28} />
      </div>

      {progressValue !== undefined && progressColor && (
        <div
          style={{
            height: 2,
            background: 'var(--border)',
            borderRadius: 1,
            overflow: 'hidden',
          }}
        >
          <div
            className="bar-animated"
            style={{
              height: '100%',
              width: `${progressValue}%`,
              background: progressColor,
              borderRadius: 1,
            }}
          />
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {sub && (
          <span style={{ fontSize: 12, color: subColor }}>{sub}</span>
        )}
        {change && (
          <span
            style={{
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
              color: changePositive ? '#22c55e' : 'var(--red)',
              background: changePositive ? 'rgba(34, 197, 94, 0.08)' : 'rgba(239, 68, 68, 0.08)',
              border: `1px solid ${changePositive ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`,
              padding: '2px 6px',
              borderRadius: 4,
            }}
          >
            {change}
          </span>
        )}
      </div>
    </div>
  );
}

// --- Section wrapper ---

function Section({
  label,
  sublabel,
  children,
}: {
  label: string;
  sublabel?: string;
  children: React.ReactNode;
}) {
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
          padding: '12px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'baseline',
          gap: 10,
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</span>
        {sublabel && (
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{sublabel}</span>
        )}
      </div>
      <div style={{ padding: '14px 16px' }}>{children}</div>
    </div>
  );
}

// --- Dept Health Bar ---

function DeptHealthBar({
  dept,
}: {
  dept: { name: string; health: number; color: string; agents: number; tasks: number; cost: number };
}) {
  const isWarn = dept.health < 50;
  const barColor = isWarn ? 'var(--amber)' : 'var(--accent)';

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '100px 1fr 80px 70px 60px',
        alignItems: 'center',
        gap: 12,
        padding: '8px 0',
        borderBottom: '1px solid rgba(30,30,46,0.6)',
      }}
    >
      <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>
        {dept.name}
      </span>

      <div style={{ position: 'relative', height: 6, background: 'var(--border)', borderRadius: 3 }}>
        <div
          className="bar-animated"
          style={{
            position: 'absolute',
            height: '100%',
            width: `${dept.health}%`,
            background: barColor,
            borderRadius: 3,
            boxShadow: isWarn ? undefined : '0 0 8px rgba(34,211,238,0.3)',
          }}
        />
      </div>

      <span
        style={{
          fontSize: 12,
          fontFamily: 'var(--font-mono)',
          color: isWarn ? 'var(--amber)' : 'var(--accent)',
          fontWeight: 600,
          textAlign: 'right',
        }}
      >
        {dept.health}%
      </span>

      <span style={{ fontSize: 11, color: 'var(--text-dim)', textAlign: 'center' }}>
        {dept.agents}a · {dept.tasks}t
      </span>

      <span
        style={{
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-dim)',
          textAlign: 'right',
        }}
      >
        ${dept.cost.toFixed(2)}
      </span>
    </div>
  );
}

// --- Activity Stream ---

const actionColors: Record<string, string> = {
  complete: '#22d3ee',
  approve: '#22c55e',
  delegate: '#a78bfa',
  start: 'var(--accent)',
  submit: '#60a5fa',
  flag: 'var(--amber)',
};

const actionLabels: Record<string, string> = {
  complete: 'completed',
  approve: 'approved',
  delegate: 'delegated',
  start: 'started',
  submit: 'submitted',
  flag: 'flagged',
};

function ActivityStream() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {activityFeed.map((item, i) => (
        <div
          key={item.id}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            padding: '7px 0',
            borderBottom: i < activityFeed.length - 1 ? '1px solid rgba(30,30,46,0.5)' : 'none',
            animationDelay: `${i * 30}ms`,
          }}
          className="fade-in-up"
        >
          {/* Timeline dot */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, paddingTop: 4 }}>
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: actionColors[item.type] ?? 'var(--text-dim)',
                flexShrink: 0,
              }}
            />
            {i < activityFeed.length - 1 && (
              <div style={{ width: 1, flex: 1, background: 'var(--border)', marginTop: 4, minHeight: 14 }} />
            )}
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', flexShrink: 0 }}>
                {item.agent}
              </span>
              <span
                style={{
                  fontSize: 11,
                  color: actionColors[item.type] ?? 'var(--text-secondary)',
                  flexShrink: 0,
                }}
              >
                {actionLabels[item.type] ?? item.action}
              </span>
              <span
                style={{
                  fontSize: 12,
                  color: 'var(--text-secondary)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {item.task}
              </span>
              {item.to && (
                <span style={{ fontSize: 11, color: 'var(--text-dim)', flexShrink: 0 }}>
                  → {item.to}
                </span>
              )}
            </div>
          </div>

          <span
            style={{
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-dim)',
              flexShrink: 0,
              paddingTop: 2,
            }}
          >
            {item.time}
          </span>
        </div>
      ))}
    </div>
  );
}

// --- Budget Burn Chart ---

const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string; color: string }>; label?: string }) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-bright)',
        borderRadius: 6,
        padding: '8px 12px',
        fontSize: 11,
        fontFamily: 'var(--font-mono)',
      }}
    >
      <div style={{ color: 'var(--text-dim)', marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name === 'actual' ? 'Actual' : 'Forecast'}: ${p.value?.toFixed(2)}
        </div>
      ))}
    </div>
  );
};

function BudgetBurnChart() {
  return (
    <div>
      <div style={{ display: 'flex', gap: 24, marginBottom: 12, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
        <div>
          <span style={{ color: 'var(--text-dim)' }}>remaining </span>
          <span style={{ color: 'var(--accent)', fontWeight: 600 }}>$257.83 (33%)</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-dim)' }}>at this rate </span>
          <span style={{ color: 'var(--amber)', fontWeight: 600 }}>~4.2 days left</span>
        </div>
      </div>
      <div style={{ height: 160 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={budgetBurnData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="actualGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.08} />
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="day"
              tick={{ fontSize: 10, fill: '#475569', fontFamily: 'var(--font-mono)' }}
              axisLine={{ stroke: '#1e1e2e' }}
              tickLine={false}
              interval={2}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#475569', fontFamily: 'var(--font-mono)' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `$${v}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              x="Mar 23"
              stroke="#2a2a3e"
              strokeDasharray="3 3"
              label={{ value: 'today', fill: '#475569', fontSize: 9, fontFamily: 'var(--font-mono)' }}
            />
            <Area
              type="monotone"
              dataKey="actual"
              name="actual"
              stroke="#22d3ee"
              strokeWidth={2}
              fill="url(#actualGrad)"
              connectNulls={false}
              dot={false}
              activeDot={{ r: 3, fill: '#22d3ee' }}
            />
            <Area
              type="monotone"
              dataKey="forecast"
              name="forecast"
              stroke="#f59e0b"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              fill="url(#forecastGrad)"
              connectNulls={false}
              dot={false}
              activeDot={{ r: 3, fill: '#f59e0b' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
        <span><span style={{ color: '#22d3ee' }}>—</span> Actual spend</span>
        <span><span style={{ color: '#f59e0b' }}>- -</span> Forecast</span>
        <span style={{ marginLeft: 'auto' }}>Budget: $300/mo</span>
      </div>
    </div>
  );
}
