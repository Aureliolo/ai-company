import { ReactNode } from 'react';
import { StatusBar } from './StatusBar';
import { Sidebar } from './Sidebar';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        background: 'var(--bg-base)',
        overflow: 'hidden',
      }}
    >
      <StatusBar />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar />
        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            overflowX: 'hidden',
            background: 'var(--bg-base)',
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
