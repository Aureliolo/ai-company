import { Routes, Route, Navigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import OrgChart from './pages/OrgChart';
import AgentProfile from './pages/AgentProfile';
import Layout from './components/Layout';

function Placeholder({ title }: { title: string }) {
  return (
    <Layout>
      <div
        style={{
          padding: '40px 32px',
          color: 'rgba(255,255,255,0.4)',
          fontSize: '14px',
        }}
      >
        {title} — placeholder page
      </div>
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/db/" element={<Dashboard />} />
      <Route path="/db/org" element={<OrgChart />} />
      <Route path="/db/agent" element={<AgentProfile />} />
      <Route path="/db/tasks" element={<Placeholder title="Tasks" />} />
      <Route path="/db/money" element={<Placeholder title="Money" />} />
      <Route path="/db/settings" element={<Placeholder title="Settings" />} />
      <Route path="/db/approvals" element={<Placeholder title="Approvals" />} />
      <Route path="*" element={<Navigate to="/db/" replace />} />
    </Routes>
  );
}
