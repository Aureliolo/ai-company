import { create } from 'zustand'
import { getOverviewMetrics, getTrends, getForecast } from '@/api/endpoints/analytics'
import { getBudgetConfig, listCostRecords } from '@/api/endpoints/budget'
import { listActivities } from '@/api/endpoints/activities'
import { listAgents } from '@/api/endpoints/agents'
import { wsEventToActivityItem } from '@/utils/dashboard'
import { getErrorMessage } from '@/utils/errors'
import { aggregateWeekly, type AggregationPeriod } from '@/utils/budget'
import type {
  ActivityItem,
  BudgetConfig,
  CostRecord,
  DailySummary,
  ForecastResponse,
  OverviewMetrics,
  PeriodSummary,
  TrendsResponse,
  WsEvent,
} from '@/api/types'

const MAX_BUDGET_ACTIVITIES = 30

/** Maps AggregationPeriod to the API `period` parameter for getTrends. */
const PERIOD_TO_API = {
  hourly: '7d',
  daily: '30d',
  weekly: '90d',
} as const

interface BudgetState {
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
  loading: boolean
  error: string | null

  fetchBudgetData: () => Promise<void>
  fetchOverview: () => Promise<void>
  fetchTrends: () => Promise<void>
  setAggregationPeriod: (period: AggregationPeriod) => void
  pushActivity: (item: ActivityItem) => void
  updateFromWsEvent: (event: WsEvent) => void
}

export const useBudgetStore = create<BudgetState>()((set, get) => ({
  budgetConfig: null,
  overview: null,
  forecast: null,
  costRecords: [],
  dailySummary: [],
  periodSummary: null,
  trends: null,
  activities: [],
  agentNameMap: new Map(),
  agentDeptMap: new Map(),

  aggregationPeriod: 'daily',
  loading: false,
  error: null,

  fetchBudgetData: async () => {
    set({ loading: true, error: null })
    try {
      const [overviewR, budgetR, forecastR, recordsR, trendsR, activitiesR] =
        await Promise.allSettled([
          getOverviewMetrics(),
          getBudgetConfig(),
          getForecast(),
          listCostRecords({ limit: 500 }),
          getTrends('30d', 'spend'),
          listActivities({ limit: 30 }),
        ])

      const overview = overviewR.status === 'fulfilled' ? overviewR.value : null
      const budgetConfig = budgetR.status === 'fulfilled' ? budgetR.value : null

      if (!overview || !budgetConfig) {
        const reason =
          overviewR.status === 'rejected'
            ? overviewR.reason
            : budgetR.status === 'rejected'
              ? budgetR.reason
              : null
        set({ loading: false, error: getErrorMessage(reason ?? 'Failed to load budget data') })
        return
      }

      const forecast = forecastR.status === 'fulfilled' ? forecastR.value : null
      const recordsResult = recordsR.status === 'fulfilled' ? recordsR.value : null
      const trends = trendsR.status === 'fulfilled' ? trendsR.value : null
      const activitiesData =
        activitiesR.status === 'fulfilled' ? activitiesR.value.data : []

      // Batch 2: agent metadata (non-critical)
      const agentNameMap = new Map<string, string>()
      const agentDeptMap = new Map<string, string>()
      try {
        const agentsResult = await listAgents({ limit: 100 })
        for (const agent of agentsResult.data) {
          agentNameMap.set(agent.id, agent.name)
          agentDeptMap.set(agent.id, agent.department)
        }
      } catch (err) {
        console.warn('Failed to fetch agent list for name/dept mapping:', err)
      }

      set({
        overview,
        budgetConfig,
        forecast,
        costRecords: recordsResult?.data ?? [],
        dailySummary: recordsResult?.daily_summary ?? [],
        periodSummary: recordsResult?.period_summary ?? null,
        trends,
        activities: activitiesData,
        agentNameMap,
        agentDeptMap,
        loading: false,
        error: null,
      })
    } catch (err) {
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  fetchOverview: async () => {
    try {
      const overview = await getOverviewMetrics()
      set({ overview })
    } catch {
      // Lightweight refresh -- don't surface error for polling failures
    }
  },

  fetchTrends: async () => {
    const { aggregationPeriod } = get()
    const apiPeriod = PERIOD_TO_API[aggregationPeriod]
    try {
      const result = await getTrends(apiPeriod, 'spend')
      if (aggregationPeriod === 'weekly') {
        set({
          trends: {
            ...result,
            data_points: aggregateWeekly(result.data_points),
          },
        })
      } else {
        set({ trends: result })
      }
    } catch (err) {
      console.warn('Failed to fetch trends:', err)
    }
  },

  setAggregationPeriod: (period) => {
    set({ aggregationPeriod: period })
    get().fetchTrends()
  },

  pushActivity: (item) => {
    set((state) => ({
      activities: [item, ...state.activities].slice(0, MAX_BUDGET_ACTIVITIES),
    }))
  },

  updateFromWsEvent: (event) => {
    try {
      const item = wsEventToActivityItem(event)
      get().pushActivity(item)
      if (event.event_type === 'budget.record_added') {
        get().fetchOverview()
      }
    } catch (err) {
      console.error('Failed to process WebSocket event:', err)
    }
  },
}))
