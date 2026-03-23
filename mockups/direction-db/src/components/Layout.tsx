import { ReactNode } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#0f1117' }}>
      <Sidebar />
      <div style={{ flex: 1, marginLeft: '48px' }}>
        <Header />
        <main
          style={{
            paddingTop: '48px',
            minHeight: '100vh',
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
