import { Routes, Route, Navigate } from "react-router-dom"
import { ThemeProvider } from "@/themes/provider.tsx"
import { Dashboard } from "@/pages/dashboard.tsx"
import { AgentProfile } from "@/pages/agent-profile.tsx"
import { Compare } from "@/pages/compare.tsx"
import { AppShell } from "@/layouts/app-shell.tsx"

function VariationLayout() {
  return (
    <ThemeProvider>
      <AppShell>
        <Routes>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="agent/:agentId" element={<AgentProfile />} />
          <Route path="*" element={<Navigate to="dashboard" replace />} />
        </Routes>
      </AppShell>
    </ThemeProvider>
  )
}

export function App() {
  return (
    <Routes>
      <Route path="/compare" element={<Compare />} />
      <Route path="/:variation/*" element={<VariationLayout />} />
      <Route path="*" element={<Navigate to="/a/dashboard" replace />} />
    </Routes>
  )
}
