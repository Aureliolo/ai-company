import { useParams } from 'react-router'
import { AlertTriangle, WifiOff } from 'lucide-react'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { useAgentDetailData } from '@/hooks/useAgentDetailData'
import { AgentDetailSkeleton } from './agents/AgentDetailSkeleton'
import { AgentIdentityHeader } from './agents/AgentIdentityHeader'
import { ProseInsight } from './agents/ProseInsight'
import { PerformanceMetrics } from './agents/PerformanceMetrics'
import { ToolBadges } from './agents/ToolBadges'
import { CareerTimeline } from './agents/CareerTimeline'
import { TaskHistory } from './agents/TaskHistory'
import { ActivityLog } from './agents/ActivityLog'
import { QualityScoreOverride } from './agents/QualityScoreOverride'

export default function AgentDetailPage() {
  const { agentName } = useParams<{ agentName: string }>()

  const {
    agent,
    performanceCards,
    insights,
    agentTasks,
    activity,
    activityTotal,
    careerHistory,
    loading,
    error,
    wsConnected,
    wsSetupError,
    fetchMoreActivity,
  } = useAgentDetailData(agentName ?? '')

  if (loading && !agent) {
    return <AgentDetailSkeleton />
  }

  const allowedTools = agent
    ? (Array.isArray(agent.tools['allowed'])
        ? (agent.tools['allowed'] as unknown[]).filter((t): t is string => typeof t === 'string')
        : [])
    : []

  if (!agent) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger">
        <AlertTriangle className="size-4 shrink-0" />
        {error ?? 'Agent not found.'}
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {!wsConnected && !loading && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-card text-sm text-warning">
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      <ErrorBoundary level="section">
        <AgentIdentityHeader agent={agent} />
      </ErrorBoundary>

      <ErrorBoundary level="section">
        <ProseInsight insights={insights} />
      </ErrorBoundary>

      <ErrorBoundary level="section">
        <PerformanceMetrics cards={performanceCards} />
      </ErrorBoundary>

      <ErrorBoundary level="section">
        <ToolBadges tools={allowedTools} />
      </ErrorBoundary>

      <ErrorBoundary level="section">
        {agent.id && <QualityScoreOverride agentId={agent.id} />}
      </ErrorBoundary>

      <div className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1">
        <ErrorBoundary level="section">
          <CareerTimeline events={[...careerHistory]} />
        </ErrorBoundary>
        <ErrorBoundary level="section">
          <TaskHistory tasks={agentTasks} />
        </ErrorBoundary>
      </div>

      <ErrorBoundary level="section">
        <ActivityLog
          events={[...activity]}
          total={activityTotal}
          onLoadMore={fetchMoreActivity}
        />
      </ErrorBoundary>
    </div>
  )
}
