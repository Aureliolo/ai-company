import { useCallback, useEffect, useMemo } from 'react'
import { useAgentsStore } from '@/stores/agents'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { usePolling } from '@/hooks/usePolling'
import { computePerformanceCards, generateInsights } from '@/utils/agents'
import type {
  AgentActivityEvent,
  AgentConfig,
  AgentPerformanceSummary,
  CareerEvent,
  Task,
  WsChannel,
} from '@/api/types'
import type { MetricCardProps } from '@/components/ui/metric-card'

const DETAIL_POLL_INTERVAL = 30_000
const DETAIL_CHANNELS = ['agents', 'tasks'] as const satisfies readonly WsChannel[]

export interface UseAgentDetailDataReturn {
  agent: AgentConfig | null
  performance: AgentPerformanceSummary | null
  performanceCards: Omit<MetricCardProps, 'className'>[]
  insights: string[]
  agentTasks: readonly Task[]
  activity: readonly AgentActivityEvent[]
  activityTotal: number
  careerHistory: readonly CareerEvent[]
  loading: boolean
  error: string | null
  wsConnected: boolean
  wsSetupError: string | null
  fetchMoreActivity: () => void
}

export function useAgentDetailData(agentName: string): UseAgentDetailDataReturn {
  const agent = useAgentsStore((s) => s.selectedAgent)
  const performance = useAgentsStore((s) => s.performance)
  const agentTasks = useAgentsStore((s) => s.agentTasks)
  const activity = useAgentsStore((s) => s.activity)
  const activityTotal = useAgentsStore((s) => s.activityTotal)
  const careerHistory = useAgentsStore((s) => s.careerHistory)
  const loading = useAgentsStore((s) => s.detailLoading)
  const error = useAgentsStore((s) => s.detailError)

  // Initial fetch
  useEffect(() => {
    useAgentsStore.getState().fetchAgentDetail(agentName)
    return () => {
      useAgentsStore.getState().clearDetail()
    }
  }, [agentName])

  // Polling for refreshes
  const pollFn = useCallback(async () => {
    await useAgentsStore.getState().fetchAgentDetail(agentName)
  }, [agentName])
  const polling = usePolling(pollFn, DETAIL_POLL_INTERVAL)

  useEffect(() => {
    polling.start()
    return () => polling.stop()
    // polling is a new object each render but start/stop are stable --
    // including it would restart polling on every render
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [agentName])

  // WebSocket
  const bindings: ChannelBinding[] = useMemo(
    () =>
      DETAIL_CHANNELS.map((channel) => ({
        channel,
        handler: () => {
          useAgentsStore.getState().fetchAgentDetail(agentName)
        },
      })),
    [agentName],
  )

  const { connected: wsConnected, setupError: wsSetupError } = useWebSocket({ bindings })

  // Derived data
  const performanceCards = useMemo(
    () => (performance ? computePerformanceCards(performance) : []),
    [performance],
  )

  const insights = useMemo(
    () => (agent ? generateInsights(agent, performance) : []),
    [agent, performance],
  )

  // Load more activity
  const fetchMoreActivity = useCallback(() => {
    useAgentsStore.getState().fetchMoreActivity(agentName, activity.length)
  }, [agentName, activity.length])

  return {
    agent,
    performance,
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
  }
}
