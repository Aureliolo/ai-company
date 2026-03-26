import { create } from 'zustand'
import { getOverviewMetrics, getForecast } from '@/api/endpoints/analytics'
import { getBudgetConfig } from '@/api/endpoints/budget'
import { listDepartments, getDepartmentHealth } from '@/api/endpoints/company'
import { listActivities } from '@/api/endpoints/activities'
import { computeOrgHealth, wsEventToActivityItem } from '@/utils/dashboard'
import { getErrorMessage } from '@/utils/errors'
import type {
  ActivityItem,
  BudgetConfig,
  DepartmentHealth,
  ForecastResponse,
  OverviewMetrics,
  WsEvent,
} from '@/api/types'

const MAX_ACTIVITIES = 50

interface AnalyticsState {
  overview: OverviewMetrics | null
  forecast: ForecastResponse | null
  departmentHealths: DepartmentHealth[]
  activities: ActivityItem[]
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
      const [overview, forecast, budgetConfig, activitiesResult] = await Promise.all([
        getOverviewMetrics(),
        getForecast(),
        getBudgetConfig(),
        listActivities({ limit: 20 }).catch(() => ({ data: [] as ActivityItem[] })),
      ])

      let departmentHealths: DepartmentHealth[] = []
      try {
        const deptResult = await listDepartments()
        const healthPromises = deptResult.data.map((dept) =>
          getDepartmentHealth(dept.name).catch(() => null),
        )
        const healthResults = await Promise.all(healthPromises)
        departmentHealths = healthResults.filter(
          (h): h is DepartmentHealth => h !== null,
        )
      } catch {
        // Department health endpoints may not exist yet -- degrade gracefully
      }

      const orgHealthPercent = computeOrgHealth(departmentHealths)

      set({
        overview,
        forecast,
        budgetConfig,
        departmentHealths,
        orgHealthPercent,
        activities: activitiesResult.data,
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
      // Lightweight refresh -- don't set error for polling failures
    }
  },

  pushActivity: (item) => {
    set((state) => ({
      activities: [item, ...state.activities].slice(0, MAX_ACTIVITIES),
    }))
  },

  updateFromWsEvent: (event) => {
    const item = wsEventToActivityItem(event)
    get().pushActivity(item)
  },
}))
