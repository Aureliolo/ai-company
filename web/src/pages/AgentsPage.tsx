import { AlertTriangle, WifiOff } from 'lucide-react'
import { useAgentsData } from '@/hooks/useAgentsData'
import { AgentsSkeleton } from './agents/AgentsSkeleton'
import { AgentFilters } from './agents/AgentFilters'
import { AgentGridView } from './agents/AgentGridView'

export default function AgentsPage() {
  const {
    filteredAgents,
    totalAgents,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useAgentsData()

  if (loading && totalAgents === 0) {
    return <AgentsSkeleton />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Agents</h1>
        <span className="text-sm text-muted-foreground">
          {filteredAgents.length} of {totalAgents}
        </span>
      </div>

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {!wsConnected && !loading && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-2 text-sm text-warning"
        >
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      <AgentFilters />
      <AgentGridView agents={filteredAgents} />
    </div>
  )
}
