import { useAnalyticsStore } from '@/stores/analytics'
import type { ActivityItem, WsEvent } from '@/api/types'

vi.mock('@/api/endpoints/analytics', () => ({
  getOverviewMetrics: vi.fn().mockResolvedValue({
    total_tasks: 24,
    tasks_by_status: {
      created: 2, assigned: 3, in_progress: 8, in_review: 2, completed: 5,
      blocked: 1, failed: 1, interrupted: 1, cancelled: 1,
    },
    total_agents: 10,
    total_cost_usd: 42.17,
    budget_remaining_usd: 457.83,
    budget_used_percent: 8.43,
    cost_7d_trend: [],
    active_agents_count: 5,
    idle_agents_count: 4,
  }),
  getForecast: vi.fn().mockResolvedValue({
    horizon_days: 30,
    projected_total_usd: 200,
    daily_projections: [],
    days_until_exhausted: null,
    confidence: 0.85,
    avg_daily_spend_usd: 6.5,
  }),
}))

vi.mock('@/api/endpoints/budget', () => ({
  getBudgetConfig: vi.fn().mockResolvedValue({
    total_monthly: 500,
    alerts: { warn_at: 80, critical_at: 95, hard_stop_at: 100 },
    per_task_limit: 10,
    per_agent_daily_limit: 20,
    auto_downgrade: { enabled: false, threshold: 90, downgrade_map: [], boundary: 'task_assignment' },
    reset_day: 1,
  }),
}))

vi.mock('@/api/endpoints/company', () => ({
  listDepartments: vi.fn().mockResolvedValue({ data: [], total: 0, offset: 0, limit: 50 }),
  getDepartmentHealth: vi.fn().mockResolvedValue({
    name: 'engineering',
    display_name: 'Engineering',
    health_percent: 85,
    agent_count: 4,
    task_count: 10,
    cost_usd: null,
  }),
}))

vi.mock('@/api/endpoints/activities', () => ({
  listActivities: vi.fn().mockResolvedValue({ data: [], total: 0, offset: 0, limit: 20 }),
}))

function resetStore() {
  useAnalyticsStore.setState({
    overview: null,
    forecast: null,
    departmentHealths: [],
    activities: [],
    budgetConfig: null,
    orgHealthPercent: null,
    loading: false,
    error: null,
  })
}

describe('useAnalyticsStore', () => {
  beforeEach(() => {
    resetStore()
  })

  describe('fetchDashboardData', () => {
    it('sets loading to true during fetch', async () => {
      const promise = useAnalyticsStore.getState().fetchDashboardData()
      expect(useAnalyticsStore.getState().loading).toBe(true)
      await promise
    })

    it('populates overview after fetch', async () => {
      await useAnalyticsStore.getState().fetchDashboardData()
      const state = useAnalyticsStore.getState()
      expect(state.overview).not.toBeNull()
      expect(state.overview!.total_tasks).toBe(24)
    })

    it('populates forecast after fetch', async () => {
      await useAnalyticsStore.getState().fetchDashboardData()
      expect(useAnalyticsStore.getState().forecast).not.toBeNull()
    })

    it('populates budgetConfig after fetch', async () => {
      await useAnalyticsStore.getState().fetchDashboardData()
      expect(useAnalyticsStore.getState().budgetConfig).not.toBeNull()
    })

    it('sets loading to false after fetch', async () => {
      await useAnalyticsStore.getState().fetchDashboardData()
      expect(useAnalyticsStore.getState().loading).toBe(false)
    })

    it('sets error to null on success', async () => {
      useAnalyticsStore.setState({ error: 'previous error' })
      await useAnalyticsStore.getState().fetchDashboardData()
      expect(useAnalyticsStore.getState().error).toBeNull()
    })

    it('degrades gracefully when listActivities fails', async () => {
      const { listActivities } = await import('@/api/endpoints/activities')
      vi.mocked(listActivities).mockRejectedValueOnce(new Error('Not found'))

      await useAnalyticsStore.getState().fetchDashboardData()
      const state = useAnalyticsStore.getState()
      expect(state.activities).toEqual([])
      expect(state.error).toBeNull()
    })

    it('degrades gracefully when listDepartments fails', async () => {
      const { listDepartments } = await import('@/api/endpoints/company')
      vi.mocked(listDepartments).mockRejectedValueOnce(new Error('Not found'))

      await useAnalyticsStore.getState().fetchDashboardData()
      const state = useAnalyticsStore.getState()
      expect(state.departmentHealths).toEqual([])
      expect(state.error).toBeNull()
    })

    it('populates departmentHealths when departments exist', async () => {
      const { listDepartments, getDepartmentHealth } = await import('@/api/endpoints/company')
      vi.mocked(listDepartments).mockResolvedValueOnce({
        data: [{ name: 'engineering', display_name: 'Engineering', teams: [] }],
        total: 1, offset: 0, limit: 50,
      })
      vi.mocked(getDepartmentHealth).mockResolvedValueOnce({
        name: 'engineering',
        display_name: 'Engineering',
        health_percent: 85,
        agent_count: 4,
        task_count: 10,
        cost_usd: null,
      })

      await useAnalyticsStore.getState().fetchDashboardData()
      const state = useAnalyticsStore.getState()
      expect(state.departmentHealths).toHaveLength(1)
      expect(state.departmentHealths[0]!.health_percent).toBe(85)
      expect(state.orgHealthPercent).toBe(85)
    })

    it('sets error on API failure', async () => {
      const { getOverviewMetrics } = await import('@/api/endpoints/analytics')
      vi.mocked(getOverviewMetrics).mockRejectedValueOnce(new Error('Network error'))

      await useAnalyticsStore.getState().fetchDashboardData()
      const state = useAnalyticsStore.getState()
      expect(state.error).toBe('Network error')
      expect(state.loading).toBe(false)
    })
  })

  describe('fetchOverview', () => {
    it('updates overview without resetting other state', async () => {
      const existingActivities: ActivityItem[] = [
        { id: '1', timestamp: '2026-03-26T10:00:00Z', agent_name: 'agent-a', action_type: 'task.created', description: 'test', task_id: null, department: null },
      ]
      useAnalyticsStore.setState({ activities: existingActivities })

      await useAnalyticsStore.getState().fetchOverview()
      const state = useAnalyticsStore.getState()
      expect(state.overview).not.toBeNull()
      expect(state.activities).toEqual(existingActivities)
    })
  })

  describe('pushActivity', () => {
    it('prepends an activity to the list', () => {
      const item: ActivityItem = {
        id: 'new-1', timestamp: '2026-03-26T10:00:00Z', agent_name: 'agent-a',
        action_type: 'task.created', description: 'created a task', task_id: null, department: null,
      }
      useAnalyticsStore.getState().pushActivity(item)
      expect(useAnalyticsStore.getState().activities[0]).toEqual(item)
    })

    it('caps activities at 50 items', () => {
      const items: ActivityItem[] = Array.from({ length: 50 }, (_, i) => ({
        id: `existing-${i}`, timestamp: '2026-03-26T10:00:00Z', agent_name: 'agent',
        action_type: 'task.created' as const, description: 'test', task_id: null, department: null,
      }))
      useAnalyticsStore.setState({ activities: items })

      const newItem: ActivityItem = {
        id: 'new-51', timestamp: '2026-03-26T11:00:00Z', agent_name: 'agent-new',
        action_type: 'task.updated', description: 'updated', task_id: null, department: null,
      }
      useAnalyticsStore.getState().pushActivity(newItem)

      const activities = useAnalyticsStore.getState().activities
      expect(activities).toHaveLength(50)
      expect(activities[0]!.id).toBe('new-51')
      expect(activities[49]!.id).toBe('existing-48')
    })
  })

  describe('updateFromWsEvent', () => {
    it('pushes a new activity from the event', () => {
      const event: WsEvent = {
        event_type: 'task.created',
        channel: 'tasks',
        timestamp: '2026-03-26T10:00:00Z',
        payload: { agent_name: 'agent-cto', task_id: 'task-1' },
      }
      useAnalyticsStore.getState().updateFromWsEvent(event)
      const activities = useAnalyticsStore.getState().activities
      expect(activities).toHaveLength(1)
      expect(activities[0]!.agent_name).toBe('agent-cto')
    })
  })
})
