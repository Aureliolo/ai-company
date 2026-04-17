import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  BudgetConfig,
  CostRecord,
  ForecastResponse,
  OverviewMetrics,
  TrendsResponse,
  WsEvent,
} from '@/api/types'

vi.mock('@/api/endpoints/analytics')
vi.mock('@/api/endpoints/budget')
vi.mock('@/api/endpoints/activities')
vi.mock('@/api/endpoints/agents')

import { getOverviewMetrics, getTrends, getForecast } from '@/api/endpoints/analytics'
import { getBudgetConfig, listCostRecords } from '@/api/endpoints/budget'
import { listActivities } from '@/api/endpoints/activities'
import { listAgents } from '@/api/endpoints/agents'
import { useBudgetStore } from '@/stores/budget'

// ── Mock data ──────────────────────────────────────────────

const mockOverview: OverviewMetrics = {
  total_tasks: 10,
  tasks_by_status: {} as Record<string, number>,
  total_agents: 5,
  total_cost: 42,
  budget_remaining: 58,
  budget_used_percent: 42,
  cost_7d_trend: [],
  active_agents_count: 3,
  idle_agents_count: 2,
  currency: 'EUR',
}

const mockBudgetConfig: BudgetConfig = {
  total_monthly: 100,
  alerts: { warn_at: 75, critical_at: 90, hard_stop_at: 100 },
  per_task_limit: 5,
  per_agent_daily_limit: 20,
  auto_downgrade: { enabled: false, threshold: 85, downgrade_map: [], boundary: 'task_assignment' },
  reset_day: 1,
  currency: 'EUR',
}

const mockForecast: ForecastResponse = {
  horizon_days: 14,
  projected_total: 80,
  daily_projections: [],
  days_until_exhausted: 20,
  confidence: 0.8,
  avg_daily_spend: 3,
  currency: 'EUR',
}

const mockTrends: TrendsResponse = {
  period: '30d',
  metric: 'spend',
  bucket_size: 'day',
  data_points: [{ timestamp: '2026-03-20', value: 5 }],
}

const mockCostRecord: CostRecord = {
  agent_id: 'a1',
  task_id: 't1',
  project_id: null,
  provider: 'test-provider',
  model: 'test-model-001',
  input_tokens: 100,
  output_tokens: 50,
  cost: 1.0,
  timestamp: '2026-03-20T10:00:00Z',
  call_category: 'productive',
  accuracy_effort_ratio: null,
  latency_ms: null,
  cache_hit: null,
  retry_count: null,
  retry_reason: null,
  finish_reason: null,
  success: null,
}

// ── Helpers ────────────────────────────────────────────────

function setupSuccessfulFetches() {
  vi.mocked(getOverviewMetrics).mockResolvedValue(mockOverview)
  vi.mocked(getBudgetConfig).mockResolvedValue(mockBudgetConfig)
  vi.mocked(getForecast).mockResolvedValue(mockForecast)
  vi.mocked(listCostRecords).mockResolvedValue({
    data: [mockCostRecord],
    total: 1,
    offset: 0,
    limit: 500,
    daily_summary: [],
    period_summary: {
      avg_cost: 1,
      total_cost: 1,
      total_input_tokens: 100,
      total_output_tokens: 50,
      record_count: 1,
      currency: 'EUR',
    },
    currency: 'EUR',
  })
  vi.mocked(getTrends).mockResolvedValue(mockTrends)
  vi.mocked(listActivities).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 30 })
  vi.mocked(listAgents).mockResolvedValue({
    data: [
      {
        id: 'a1',
        name: 'Alpha',
        role: 'Developer',
        department: 'engineering',
        level: 'mid',
        status: 'active',
        personality: {
          traits: [],
          communication_style: 'direct',
          risk_tolerance: 'medium',
          creativity: 'medium',
          description: 'Test agent',
          openness: 0.5,
          conscientiousness: 0.5,
          extraversion: 0.5,
          agreeableness: 0.5,
          stress_response: 0.5,
          decision_making: 'analytical',
          collaboration: 'team',
          verbosity: 'balanced',
          conflict_approach: 'collaborate',
        },
        model: {
          provider: 'test-provider',
          model_id: 'test-model-001',
          temperature: 0.7,
          max_tokens: 4096,
          fallback_model: null,
        },
        memory: { type: 'persistent', retention_days: null },
        tools: { access_level: 'standard', allowed: [], denied: [] },
        authority: {},
        autonomy_level: 'semi',
        hiring_date: '2026-01-01T00:00:00Z',
      },
    ],
    total: 1,
    offset: 0,
    limit: 100,
  })
}

// ── Tests ──────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  useBudgetStore.setState({
    budgetConfig: null,
    overview: null,
    forecast: null,
    costRecords: [],
    trends: null,
    activities: [],
    agentNameMap: new Map(),
    agentDeptMap: new Map(),
    aggregationPeriod: 'daily',
    loading: false,
    error: null,
  })
})

describe('fetchBudgetData', () => {
  it('sets loading to true at the start of fetch', () => {
    setupSuccessfulFetches()
    // Don't await -- check intermediate state
    useBudgetStore.getState().fetchBudgetData()
    expect(useBudgetStore.getState().loading).toBe(true)
  })

  it('populates all state fields on success', async () => {
    setupSuccessfulFetches()
    await useBudgetStore.getState().fetchBudgetData()
    const state = useBudgetStore.getState()
    expect(state.overview).toEqual(mockOverview)
    expect(state.budgetConfig).toEqual(mockBudgetConfig)
    expect(state.forecast).toEqual(mockForecast)
    expect(state.costRecords).toHaveLength(1)
    expect(state.trends).toEqual(mockTrends)
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('builds agentNameMap and agentDeptMap from agent list', async () => {
    setupSuccessfulFetches()
    await useBudgetStore.getState().fetchBudgetData()
    const state = useBudgetStore.getState()
    expect(state.agentNameMap.get('a1')).toBe('Alpha')
    expect(state.agentDeptMap.get('a1')).toBe('engineering')
  })

  it('sets error when getOverviewMetrics fails', async () => {
    setupSuccessfulFetches()
    vi.mocked(getOverviewMetrics).mockRejectedValue(new Error('overview down'))
    await useBudgetStore.getState().fetchBudgetData()
    const state = useBudgetStore.getState()
    expect(state.error).toBe('overview down')
    expect(state.loading).toBe(false)
  })

  it('sets error when getBudgetConfig fails', async () => {
    setupSuccessfulFetches()
    vi.mocked(getBudgetConfig).mockRejectedValue(new Error('config down'))
    await useBudgetStore.getState().fetchBudgetData()
    const state = useBudgetStore.getState()
    expect(state.error).toBe('config down')
    expect(state.loading).toBe(false)
  })

  it('degrades gracefully when getForecast fails', async () => {
    setupSuccessfulFetches()
    vi.mocked(getForecast).mockRejectedValue(new Error('no forecast'))
    await useBudgetStore.getState().fetchBudgetData()
    const state = useBudgetStore.getState()
    expect(state.forecast).toBeNull()
    expect(state.error).toBeNull()
  })

  it('degrades gracefully when listCostRecords fails', async () => {
    setupSuccessfulFetches()
    vi.mocked(listCostRecords).mockRejectedValue(new Error('no records'))
    await useBudgetStore.getState().fetchBudgetData()
    const state = useBudgetStore.getState()
    expect(state.costRecords).toEqual([])
    expect(state.error).toBeNull()
  })

  it('degrades gracefully when listAgents fails', async () => {
    setupSuccessfulFetches()
    vi.mocked(listAgents).mockRejectedValue(new Error('agents down'))
    await useBudgetStore.getState().fetchBudgetData()
    const state = useBudgetStore.getState()
    expect(state.agentNameMap.size).toBe(0)
    expect(state.agentDeptMap.size).toBe(0)
    expect(state.error).toBeNull()
  })
})

describe('fetchOverview', () => {
  it('updates overview without resetting other fields', async () => {
    useBudgetStore.setState({ forecast: mockForecast })
    vi.mocked(getOverviewMetrics).mockResolvedValue(mockOverview)
    await useBudgetStore.getState().fetchOverview()
    const state = useBudgetStore.getState()
    expect(state.overview).toEqual(mockOverview)
    expect(state.forecast).toEqual(mockForecast)
  })

  it('does not set error state when fetchOverview fails', async () => {
    vi.mocked(getOverviewMetrics).mockRejectedValue(new Error('network'))
    await useBudgetStore.getState().fetchOverview()
    expect(useBudgetStore.getState().error).toBeNull()
    expect(useBudgetStore.getState().loading).toBe(false)
  })
})

describe('fetchTrends', () => {
  it('maps daily period to 30d API call', async () => {
    useBudgetStore.setState({ aggregationPeriod: 'daily' })
    vi.mocked(getTrends).mockResolvedValue(mockTrends)
    await useBudgetStore.getState().fetchTrends()
    expect(getTrends).toHaveBeenCalledWith('30d', 'spend')
  })

  it('maps hourly period to 7d API call', async () => {
    useBudgetStore.setState({ aggregationPeriod: 'hourly' })
    vi.mocked(getTrends).mockResolvedValue(mockTrends)
    await useBudgetStore.getState().fetchTrends()
    expect(getTrends).toHaveBeenCalledWith('7d', 'spend')
  })

  it('clears trends on fetchTrends failure', async () => {
    useBudgetStore.setState({ trends: mockTrends })
    vi.mocked(getTrends).mockRejectedValue(new Error('network'))
    await useBudgetStore.getState().fetchTrends()
    expect(useBudgetStore.getState().trends).toBeNull()
  })

  it('maps weekly period to 90d API call and aggregates', async () => {
    useBudgetStore.setState({ aggregationPeriod: 'weekly' })
    vi.mocked(getTrends).mockResolvedValue({
      ...mockTrends,
      period: '90d',
      data_points: [
        { timestamp: '2026-03-23', value: 3 },
        { timestamp: '2026-03-24', value: 7 },
      ],
    })
    await useBudgetStore.getState().fetchTrends()
    expect(getTrends).toHaveBeenCalledWith('90d', 'spend')
    const state = useBudgetStore.getState()
    // Both days are in the same week, so aggregateWeekly should merge them
    expect(state.trends!.data_points).toHaveLength(1)
    expect(state.trends!.data_points[0]!.value).toBe(10)
  })
})

describe('setAggregationPeriod', () => {
  it('updates period in state', () => {
    vi.mocked(getTrends).mockResolvedValue(mockTrends)
    useBudgetStore.getState().setAggregationPeriod('hourly')
    expect(useBudgetStore.getState().aggregationPeriod).toBe('hourly')
  })

  it('calls fetchTrends when period changes', async () => {
    vi.mocked(getTrends).mockResolvedValue(mockTrends)
    useBudgetStore.getState().setAggregationPeriod('weekly')
    await vi.waitFor(() => {
      expect(getTrends).toHaveBeenCalledWith('90d', 'spend')
    })
  })
})

describe('pushActivity', () => {
  it('prepends and caps at 30', () => {
    const existing = Array.from({ length: 30 }, (_, i) => ({
      id: `old-${i}`,
      timestamp: '2026-03-20T10:00:00Z',
      agent_name: 'Bot',
      action_type: 'budget.record_added' as const,
      description: 'recorded a cost',
      task_id: null,
      department: null,
    }))
    useBudgetStore.setState({ activities: existing })
    useBudgetStore.getState().pushActivity({
      id: 'new',
      timestamp: '2026-03-20T11:00:00Z',
      agent_name: 'Bot',
      action_type: 'budget.alert',
      description: 'alert',
      task_id: null,
      department: null,
    })
    const { activities } = useBudgetStore.getState()
    expect(activities).toHaveLength(30)
    expect(activities[0]!.id).toBe('new')
  })
})

describe('updateFromWsEvent', () => {
  it('converts event to activity and pushes it', () => {
    const event: WsEvent = {
      event_type: 'budget.record_added',
      channel: 'budget',
      timestamp: '2026-03-20T10:00:00Z',
      payload: { agent_name: 'CFO Bot' },
    }
    useBudgetStore.getState().updateFromWsEvent(event)
    const { activities } = useBudgetStore.getState()
    expect(activities).toHaveLength(1)
    expect(activities[0]!.agent_name).toBe('CFO Bot')
  })

  it('triggers fetchOverview when event_type is budget.record_added', async () => {
    vi.mocked(getOverviewMetrics).mockResolvedValue(mockOverview)
    const event: WsEvent = {
      event_type: 'budget.record_added',
      channel: 'budget',
      timestamp: '2026-03-20T10:00:00Z',
      payload: { agent_name: 'CFO Bot' },
    }
    useBudgetStore.getState().updateFromWsEvent(event)
    await vi.waitFor(() => {
      expect(getOverviewMetrics).toHaveBeenCalled()
    })
  })
})
