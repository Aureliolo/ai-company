import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { OrgChart } from './pages/OrgChart';
import { AgentProfile } from './pages/AgentProfile';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/cd/" element={<Dashboard />} />
        <Route path="/cd/org" element={<OrgChart />} />
        <Route path="/cd/agent" element={<AgentProfile />} />
        <Route path="*" element={<Navigate to="/cd/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
