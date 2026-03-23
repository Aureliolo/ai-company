import { Link } from 'react-router-dom';
import { companyStats } from '../data/mockData';

export default function Header() {
  return (
    <header
      style={{
        height: '48px',
        backgroundColor: '#0f1117',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingLeft: '64px',
        paddingRight: '24px',
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 99,
      }}
    >
      {/* Left: Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span
          style={{
            fontWeight: 600,
            fontSize: '14px',
            color: 'rgba(255,255,255,0.9)',
            letterSpacing: '-0.01em',
          }}
        >
          SynthOrg
        </span>
        <span
          style={{
            fontSize: '12px',
            color: 'rgba(255,255,255,0.3)',
            fontWeight: 400,
          }}
        >
          {companyStats.name}
        </span>
      </div>

      {/* Right: Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        {/* Connection indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: '#10b981',
            }}
          />
          <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.4)', fontWeight: 400 }}>
            Live
          </span>
        </div>

        {/* Pending approvals */}
        <Link
          to="/db/approvals"
          style={{
            fontSize: '12px',
            color: '#6366f1',
            fontWeight: 500,
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
          }}
        >
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '16px',
              height: '16px',
              borderRadius: '50%',
              backgroundColor: 'rgba(99,102,241,0.2)',
              fontSize: '10px',
              fontWeight: 600,
              color: '#6366f1',
            }}
          >
            {companyStats.pendingApprovals}
          </span>
          pending
        </Link>
      </div>
    </header>
  );
}
