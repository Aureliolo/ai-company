import { NavLink } from 'react-router-dom';

interface NavItem {
  path: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  {
    path: '/db/',
    label: 'Overview',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    path: '/db/org',
    label: 'Org Chart',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="4" r="2" />
        <circle cx="5" cy="16" r="2" />
        <circle cx="19" cy="16" r="2" />
        <line x1="12" y1="6" x2="12" y2="11" />
        <line x1="12" y1="11" x2="5" y2="14" />
        <line x1="12" y1="11" x2="19" y2="14" />
      </svg>
    ),
  },
  {
    path: '/db/agent',
    label: 'People',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="7" r="3" />
        <path d="M5 20c0-3.87 3.13-7 7-7s7 3.13 7 7" />
      </svg>
    ),
  },
];

const bottomItems: NavItem[] = [
  {
    path: '/db/tasks',
    label: 'Tasks',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 12l2 2 4-4" />
        <rect x="3" y="3" width="18" height="18" rx="2" />
      </svg>
    ),
  },
  {
    path: '/db/money',
    label: 'Money',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v10M9.5 9.5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5c0 2.5-5 2.5-5 5 0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5" />
      </svg>
    ),
  },
  {
    path: '/db/settings',
    label: 'Settings',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  return (
    <nav
      style={{
        width: '48px',
        minHeight: '100vh',
        backgroundColor: '#0f1117',
        borderRight: '1px solid rgba(255,255,255,0.05)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        paddingTop: '16px',
        paddingBottom: '16px',
        gap: '4px',
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        zIndex: 100,
      }}
    >
      {/* Logo mark */}
      <div style={{ marginBottom: '20px', padding: '4px' }}>
        <div
          style={{
            width: '28px',
            height: '28px',
            backgroundColor: '#6366f1',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
            <circle cx="5" cy="5" r="3" />
            <circle cx="19" cy="5" r="3" />
            <circle cx="12" cy="19" r="3" />
            <line x1="5" y1="5" x2="12" y2="19" stroke="white" strokeWidth="2" />
            <line x1="19" y1="5" x2="12" y2="19" stroke="white" strokeWidth="2" />
            <line x1="5" y1="5" x2="19" y2="5" stroke="white" strokeWidth="2" />
          </svg>
        </div>
      </div>

      {/* Main nav items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', width: '100%', alignItems: 'center', flex: 1 }}>
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/db/'}
            title={item.label}
            style={({ isActive }) => ({
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: isActive ? '#6366f1' : 'rgba(255,255,255,0.35)',
              backgroundColor: isActive ? 'rgba(99,102,241,0.12)' : 'transparent',
              textDecoration: 'none',
              position: 'relative',
              transition: 'color 200ms ease, background-color 200ms ease',
            })}
          >
            {item.icon}
          </NavLink>
        ))}
      </div>

      {/* Bottom nav items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', width: '100%', alignItems: 'center' }}>
        {bottomItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            title={item.label}
            style={({ isActive }) => ({
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: isActive ? '#6366f1' : 'rgba(255,255,255,0.35)',
              backgroundColor: isActive ? 'rgba(99,102,241,0.12)' : 'transparent',
              textDecoration: 'none',
              transition: 'color 200ms ease, background-color 200ms ease',
            })}
          >
            {item.icon}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
