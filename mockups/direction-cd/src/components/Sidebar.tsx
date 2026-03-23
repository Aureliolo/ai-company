import { Link, useLocation } from 'react-router-dom';

const navItems = [
  { label: 'Overview', href: '/cd/', icon: GridIcon },
  { label: 'Org Chart', href: '/cd/org', icon: OrgIcon },
  { label: 'Agents', href: '/cd/agent', icon: AgentIcon },
  { label: 'Tasks', href: '#', icon: TaskIcon },
  { label: 'Budget', href: '#', icon: BudgetIcon },
  { label: 'Approvals', href: '#', icon: ApprovalIcon, badge: 3 },
  { label: 'Messages', href: '#', icon: MessageIcon },
  { label: 'Meetings', href: '#', icon: MeetingIcon },
  { label: 'Providers', href: '#', icon: ProviderIcon },
  { label: 'Settings', href: '#', icon: SettingsIcon },
];

export function Sidebar() {
  const location = useLocation();

  return (
    <aside
      style={{
        width: 200,
        flexShrink: 0,
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Company name */}
      <div
        style={{
          padding: '16px 16px 12px',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: 'rgba(34, 211, 238, 0.12)',
              border: '1px solid rgba(34, 211, 238, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span style={{ color: 'var(--accent)', fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>N</span>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.2 }}>
              Nexus Dynamics
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 1 }}>12 agents • Active</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {navItems.map(({ label, href, icon: Icon, badge }) => {
          const isActive =
            href !== '#' &&
            (href === '/cd/'
              ? location.pathname === '/cd/' || location.pathname === '/cd'
              : location.pathname.startsWith(href));

          return (
            <Link
              key={label}
              to={href}
              className={`nav-item${isActive ? ' active' : ''}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 16px',
                textDecoration: 'none',
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                fontSize: 13,
                fontWeight: isActive ? 500 : 400,
                position: 'relative',
              }}
            >
              <Icon
                size={15}
                color={isActive ? 'var(--accent)' : 'var(--text-dim)'}
              />
              <span style={{ flex: 1 }}>{label}</span>
              {badge && (
                <span
                  style={{
                    background: 'rgba(245, 158, 11, 0.15)',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    color: 'var(--amber)',
                    fontSize: 10,
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 600,
                    padding: '1px 5px',
                    borderRadius: 3,
                    lineHeight: 1.4,
                  }}
                >
                  {badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Cmd+K search */}
      <div
        style={{
          padding: '12px 12px 16px',
          borderTop: '1px solid var(--border)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '6px 10px',
            cursor: 'pointer',
            transition: 'border-color 200ms ease',
          }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-bright)')}
          onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
        >
          <SearchIcon size={12} color="var(--text-dim)" />
          <span style={{ fontSize: 12, color: 'var(--text-dim)', flex: 1 }}>Search...</span>
          <span
            style={{
              fontSize: 10,
              color: 'var(--text-dim)',
              fontFamily: 'var(--font-mono)',
              background: 'var(--border)',
              padding: '1px 4px',
              borderRadius: 3,
            }}
          >
            ⌘K
          </span>
        </div>
      </div>
    </aside>
  );
}

// --- Inline icon components ---

function GridIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1" stroke={color} strokeWidth="1.25" />
      <rect x="9" y="1" width="6" height="6" rx="1" stroke={color} strokeWidth="1.25" />
      <rect x="1" y="9" width="6" height="6" rx="1" stroke={color} strokeWidth="1.25" />
      <rect x="9" y="9" width="6" height="6" rx="1" stroke={color} strokeWidth="1.25" />
    </svg>
  );
}
function OrgIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="5" y="1" width="6" height="4" rx="1" stroke={color} strokeWidth="1.25" />
      <rect x="1" y="11" width="4" height="4" rx="1" stroke={color} strokeWidth="1.25" />
      <rect x="6" y="11" width="4" height="4" rx="1" stroke={color} strokeWidth="1.25" />
      <rect x="11" y="11" width="4" height="4" rx="1" stroke={color} strokeWidth="1.25" />
      <line x1="8" y1="5" x2="8" y2="9" stroke={color} strokeWidth="1.25" />
      <line x1="3" y1="9" x2="13" y2="9" stroke={color} strokeWidth="1.25" />
      <line x1="3" y1="9" x2="3" y2="11" stroke={color} strokeWidth="1.25" />
      <line x1="8" y1="9" x2="8" y2="11" stroke={color} strokeWidth="1.25" />
      <line x1="13" y1="9" x2="13" y2="11" stroke={color} strokeWidth="1.25" />
    </svg>
  );
}
function AgentIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="5" r="3" stroke={color} strokeWidth="1.25" />
      <path d="M2 14c0-3.314 2.686-6 6-6s6 2.686 6 6" stroke={color} strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}
function TaskIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="2" y="2" width="12" height="12" rx="1.5" stroke={color} strokeWidth="1.25" />
      <line x1="5" y1="6" x2="11" y2="6" stroke={color} strokeWidth="1.25" strokeLinecap="round" />
      <line x1="5" y1="9" x2="9" y2="9" stroke={color} strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}
function BudgetIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6" stroke={color} strokeWidth="1.25" />
      <path d="M8 4v1m0 6v1M6 8h1.5c.828 0 1.5-.448 1.5-1s-.672-1-1.5-1S6 5.448 6 5" stroke={color} strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}
function ApprovalIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M3 8l3.5 3.5L13 4" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function MessageIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M2 3h12v8H9l-3 2v-2H2V3z" stroke={color} strokeWidth="1.25" strokeLinejoin="round" />
    </svg>
  );
}
function MeetingIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="2" y="3" width="12" height="10" rx="1.5" stroke={color} strokeWidth="1.25" />
      <line x1="5" y1="1" x2="5" y2="4" stroke={color} strokeWidth="1.25" strokeLinecap="round" />
      <line x1="11" y1="1" x2="11" y2="4" stroke={color} strokeWidth="1.25" strokeLinecap="round" />
      <line x1="2" y1="7" x2="14" y2="7" stroke={color} strokeWidth="1.25" />
    </svg>
  );
}
function ProviderIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2" stroke={color} strokeWidth="1.25" />
      <circle cx="8" cy="8" r="5.5" stroke={color} strokeWidth="1.25" />
      <line x1="8" y1="2.5" x2="8" y2="5.5" stroke={color} strokeWidth="1.25" />
      <line x1="8" y1="10.5" x2="8" y2="13.5" stroke={color} strokeWidth="1.25" />
      <line x1="2.5" y1="8" x2="5.5" y2="8" stroke={color} strokeWidth="1.25" />
      <line x1="10.5" y1="8" x2="13.5" y2="8" stroke={color} strokeWidth="1.25" />
    </svg>
  );
}
function SettingsIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2.5" stroke={color} strokeWidth="1.25" />
      <path d="M8 1.5v1.2M8 13.3v1.2M1.5 8h1.2M13.3 8h1.2M3.6 3.6l.85.85M11.55 11.55l.85.85M3.6 12.4l.85-.85M11.55 4.45l.85-.85" stroke={color} strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  );
}
function SearchIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="7" cy="7" r="4.5" stroke={color} strokeWidth="1.5" />
      <line x1="10.5" y1="10.5" x2="14" y2="14" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
