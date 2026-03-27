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
const EMPTY_BINDINGS: ChannelBinding[] = []

const EMPTY_RETURN: UseAgentDetailDataReturn = {
  agent: null,
  performance: null,
  performanceCards: [],
  insights: [],
  agentTasks: [],
  activity: [],
  activityTotal: 0,
  careerHistory: [],
  loading: false,
  error: null,
  wsConnected: false,
  wsSetupError: null,
  fetchMoreActivity: () => {},
}

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

  // Initial fetch -- skip when agentName is empty (missing route param)
  useEffect(() => {
    if (!agentName) {
      useAgentsStore.getState().clearDetail()
      return
    }
    useAgentsStore.getState().fetchAgentDetail(agentName)
    return () => {
      useAgentsStore.getState().clearDetail()
    }
  }, [agentName])

  // Polling for refreshes -- only when agentName is truthy
  const pollFn = useCallback(async () => {
    if (!agentName) return
    await useAgentsStore.getState().fetchAgentDetail(agentName)
  }, [agentName])
  const polling = usePolling(pollFn, DETAIL_POLL_INTERVAL)

  useEffect(() => {
    if (!agentName) return
    polling.start()
    return () => polling.stop()
    // polling is a new object each render but start/stop are stable --
    // including it would restart polling on every render
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [agentName])

  // WebSocket -- only bind when agentName is truthy
  const bindings: ChannelBinding[] = useMemo(
    () =>
      agentName
        ? DETAIL_CHANNELS.map((channel) => ({
            channel,
            handler: () => {
              useAgentsStore.getState().fetchAgentDetail(agentName)
            },
          }))
        : EMPTY_BINDINGS,
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

  // Load more activity -- store-level activityLoading prevents duplicates
  const fetchMoreActivity = useCallback(() => {
    if (!agentName) return
    useAgentsStore.getState().fetchMoreActivity(agentName, activity.length)
  }, [agentName, activity.length])

  if (!agentName) return EMPTY_RETURN

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
