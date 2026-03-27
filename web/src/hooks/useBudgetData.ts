import { useCallback, useEffect, useMemo } from 'react'
import { useBudgetStore } from '@/stores/budget'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { usePolling } from '@/hooks/usePolling'
import type {
  ActivityItem,
  BudgetConfig,
  CostRecord,
  DailySummary,
  ForecastResponse,
  OverviewMetrics,
  PeriodSummary,
  TrendsResponse,
  WsChannel,
  WsEvent,
} from '@/api/types'
import type { AggregationPeriod } from '@/utils/budget'

const BUDGET_POLL_INTERVAL = 30_000
const BUDGET_CHANNELS = ['budget', 'system'] as const satisfies readonly WsChannel[]

export interface UseBudgetDataReturn {
  budgetConfig: BudgetConfig | null
  overview: OverviewMetrics | null
  forecast: ForecastResponse | null
  costRecords: readonly CostRecord[]
  dailySummary: readonly DailySummary[]
  periodSummary: PeriodSummary | null
  trends: TrendsResponse | null
  activities: readonly ActivityItem[]
  agentNameMap: ReadonlyMap<string, string>
  agentDeptMap: ReadonlyMap<string, string>
  aggregationPeriod: AggregationPeriod
  setAggregationPeriod: (period: AggregationPeriod) => void
  loading: boolean
  error: string | null
  wsConnected: boolean
  wsSetupError: string | null
}

export function useBudgetData(): UseBudgetDataReturn {
  // Individual selectors to avoid unnecessary re-renders
  const budgetConfig = useBudgetStore((s) => s.budgetConfig)
  const overview = useBudgetStore((s) => s.overview)
  const forecast = useBudgetStore((s) => s.forecast)
  const costRecords = useBudgetStore((s) => s.costRecords)
  const dailySummary = useBudgetStore((s) => s.dailySummary)
  const periodSummary = useBudgetStore((s) => s.periodSummary)
  const trends = useBudgetStore((s) => s.trends)
  const activities = useBudgetStore((s) => s.activities)
  const agentNameMap = useBudgetStore((s) => s.agentNameMap)
  const agentDeptMap = useBudgetStore((s) => s.agentDeptMap)
  const aggregationPeriod = useBudgetStore((s) => s.aggregationPeriod)
  const setAggregationPeriod = useBudgetStore((s) => s.setAggregationPeriod)
  const loading = useBudgetStore((s) => s.loading)
  const error = useBudgetStore((s) => s.error)

  // Initial fetch on mount
  useEffect(() => {
    useBudgetStore.getState().fetchBudgetData()
  }, [])

  // Polling for lightweight overview refresh
  const pollFn = useCallback(async () => {
    await useBudgetStore.getState().fetchOverview()
  }, [])
  const polling = usePolling(pollFn, BUDGET_POLL_INTERVAL)
  useEffect(() => {
    polling.start()
    return () => polling.stop()
  }, [polling])

  // WebSocket bindings
  const bindings: ChannelBinding[] = useMemo(
    () =>
      BUDGET_CHANNELS.map((channel) => ({
        channel,
        handler: (event: WsEvent) => {
          useBudgetStore.getState().updateFromWsEvent(event)
        },
      })),
    [],
  )
  const { connected: wsConnected, setupError: wsSetupError } = useWebSocket({
    bindings,
  })

  return {
    budgetConfig,
    overview,
    forecast,
    costRecords,
    dailySummary,
    periodSummary,
    trends,
    activities,
    agentNameMap,
    agentDeptMap,
    aggregationPeriod,
    setAggregationPeriod,
    loading,
    error,
    wsConnected,
    wsSetupError,
  }
}
