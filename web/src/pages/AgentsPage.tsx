import { useAgentsData } from '@/hooks/useAgentsData'
import { ErrorBanner } from '@/components/ui/error-banner'
import { ListHeader } from '@/components/ui/list-header'
import { formatNumber } from '@/utils/format'
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
    <div className="space-y-section-gap">
      <ListHeader
        title="Agents"
        count={filteredAgents.length}
        countLabel={
          filteredAgents.length === totalAgents
            ? undefined
            : `${formatNumber(filteredAgents.length)} of ${formatNumber(totalAgents)}`
        }
      />

      {error && (
        <ErrorBanner severity="error" title="Could not load agents" description={error} />
      )}

      {!wsConnected && !loading && (
        <ErrorBanner
          variant="offline"
          title="Real-time updates disconnected"
          description={wsSetupError ?? 'Data may be stale until the connection recovers.'}
        />
      )}

      <AgentFilters />
      <AgentGridView agents={filteredAgents} />
    </div>
  )
}
