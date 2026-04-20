import { create } from 'zustand'
import { getOverviewMetrics, getForecast } from '@/api/endpoints/analytics'
import { getBudgetConfig } from '@/api/endpoints/budget'
import { listDepartments, getDepartmentHealth } from '@/api/endpoints/company'
import { listActivities } from '@/api/endpoints/activities'
import { computeOrgHealth, wsEventToActivityItem } from '@/utils/dashboard'
import { getErrorMessage } from '@/utils/errors'
import { createLogger } from '@/lib/logger'
import type {
  ActivityItem,
  DepartmentHealth,
  ForecastResponse,
  OverviewMetrics,
} from '@/api/types/analytics'
import type { BudgetConfig } from '@/api/types/budget'
import type { WsEvent } from '@/api/types/websocket'

const log = createLogger('analytics')

const MAX_ACTIVITIES = 50

interface AnalyticsState {
  overview: OverviewMetrics | null
  forecast: ForecastResponse | null
  departmentHealths: readonly DepartmentHealth[]
  activities: readonly ActivityItem[]
  budgetConfig: BudgetConfig | null
  orgHealthPercent: number | null
  loading: boolean
  error: string | null
  fetchDashboardData: () => Promise<void>
  fetchOverview: () => Promise<void>
  pushActivity: (item: ActivityItem) => void
  updateFromWsEvent: (event: WsEvent) => void
}

export const useAnalyticsStore = create<AnalyticsState>()((set, get) => ({
  overview: null,
  forecast: null,
  departmentHealths: [],
  activities: [],
  budgetConfig: null,
  orgHealthPercent: null,
  loading: false,
  error: null,

  fetchDashboardData: async () => {
    set({ loading: true, error: null })
    try {
      const [overviewResult, forecastResult, budgetResult, activitiesResult] =
        await Promise.allSettled([
          getOverviewMetrics(),
          getForecast(),
          getBudgetConfig(),
          listActivities({ limit: 20 }),
        ])

      const overview = overviewResult.status === 'fulfilled' ? overviewResult.value : null
      const forecast = forecastResult.status === 'fulfilled' ? forecastResult.value : null
      const budgetConfig = budgetResult.status === 'fulfilled' ? budgetResult.value : null
      const activitiesData =
        activitiesResult.status === 'fulfilled' ? activitiesResult.value.data : []

      if (!overview) {
        // Overview is the critical dataset -- if it fails, surface the error
        const reason = overviewResult.status === 'rejected' ? overviewResult.reason : null
        set({ loading: false, error: getErrorMessage(reason ?? 'Failed to load overview') })
        return
      }

      let departmentHealths: DepartmentHealth[] = []
      try {
        const deptResult = await listDepartments({ limit: 100 })
        const healthPromises = deptResult.data.map((dept) =>
          getDepartmentHealth(dept.name).catch((err: unknown) => {
            log.warn('Failed to fetch health for dept:', dept.name, err)
            return null
          }),
        )
        const healthResults = await Promise.all(healthPromises)
        departmentHealths = healthResults.filter(
          (h): h is DepartmentHealth => h !== null,
        )
      } catch (err) {
        log.warn('Failed to fetch department list:', getErrorMessage(err))
      }

      const orgHealthPercent = computeOrgHealth(departmentHealths)

      set({
        overview,
        forecast,
        budgetConfig,
        departmentHealths,
        orgHealthPercent,
        activities: activitiesData,
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
    } catch (err) {
      log.warn('Failed to refresh overview (polling):', getErrorMessage(err))
    }
  },

  pushActivity: (item) => {
    set((state) => ({
      activities: [item, ...state.activities].slice(0, MAX_ACTIVITIES),
    }))
  },

  updateFromWsEvent: (event) => {
    try {
      const item = wsEventToActivityItem(event)
      get().pushActivity(item)
    } catch (err) {
      log.error('Failed to process WebSocket event:', err)
    }
  },
}))
