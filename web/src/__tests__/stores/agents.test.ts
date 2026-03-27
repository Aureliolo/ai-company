import { useAgentsStore } from '@/stores/agents'
import type { AgentConfig, AgentPerformanceSummary } from '@/api/types'

vi.mock('@/api/endpoints/agents', () => ({
  listAgents: vi.fn(),
  getAgent: vi.fn(),
  getAgentPerformance: vi.fn(),
  getAgentActivity: vi.fn(),
  getAgentHistory: vi.fn(),
}))

vi.mock('@/api/endpoints/tasks', () => ({
  listTasks: vi.fn(),
}))

const { listAgents, getAgent, getAgentPerformance, getAgentActivity, getAgentHistory } =
  await import('@/api/endpoints/agents')
const { listTasks } = await import('@/api/endpoints/tasks')

function makeAgent(overrides: Partial<AgentConfig> = {}): AgentConfig {
  return {
    id: 'agent-001',
    name: 'Alice Smith',
    role: 'Software Engineer',
    department: 'engineering',
    level: 'senior',
    status: 'active',
    personality: {
      traits: ['analytical'],
      communication_style: 'direct',
      risk_tolerance: 'medium',
      creativity: 'high',
      description: 'test',
      openness: 0.8,
      conscientiousness: 0.7,
      extraversion: 0.5,
      agreeableness: 0.6,
      stress_response: 0.9,
      decision_making: 'analytical',
      collaboration: 'team',
      verbosity: 'balanced',
      conflict_approach: 'collaborate',
    },
    model: {
      provider: 'test-provider',
      model_id: 'test-large-001',
      temperature: 0.7,
      max_tokens: 4096,
      fallback_model: null,
    },
    skills: { primary: ['python'], secondary: [] },
    memory: { type: 'persistent', retention_days: null },
    tools: { access_level: 'standard', allowed: ['git'], denied: [] },
    autonomy_level: 'semi',
    hiring_date: '2026-01-15T00:00:00Z',
    ...overrides,
  }
}

function makePerformance(): AgentPerformanceSummary {
  return {
    agent_name: 'Alice Smith',
    tasks_completed_total: 50,
    tasks_completed_7d: 5,
    tasks_completed_30d: 20,
    avg_completion_time_seconds: 1800,
    success_rate_percent: 90,
    cost_per_task_usd: 0.25,
    quality_score: 7.5,
    collaboration_score: 8.0,
    trend_direction: 'stable',
    windows: [],
    trends: [],
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  // Reset store to initial state
  useAgentsStore.setState({
    agents: [],
    totalAgents: 0,
    listLoading: false,
    listError: null,
    searchQuery: '',
    departmentFilter: null,
    levelFilter: null,
    statusFilter: null,
    sortBy: 'name',
    sortDirection: 'asc',
    selectedAgent: null,
    performance: null,
    agentTasks: [],
    activity: [],
    activityTotal: 0,
    careerHistory: [],
    detailLoading: false,
    detailError: null,
  })
})

describe('fetchAgents', () => {
  it('sets agents on success', async () => {
    const agents = [makeAgent(), makeAgent({ name: 'Bob Jones' })]
    vi.mocked(listAgents).mockResolvedValue({ data: agents, total: 2, offset: 0, limit: 200 })

    await useAgentsStore.getState().fetchAgents()

    const state = useAgentsStore.getState()
    expect(state.agents).toHaveLength(2)
    expect(state.totalAgents).toBe(2)
    expect(state.listLoading).toBe(false)
    expect(state.listError).toBeNull()
  })

  it('sets error on failure', async () => {
    vi.mocked(listAgents).mockRejectedValue(new Error('Network error'))

    await useAgentsStore.getState().fetchAgents()

    const state = useAgentsStore.getState()
    expect(state.agents).toHaveLength(0)
    expect(state.listLoading).toBe(false)
    expect(state.listError).toBeTruthy()
  })

  it('sets loading to true during fetch', async () => {
    let resolvePromise!: (value: { data: AgentConfig[]; total: number; offset: number; limit: number }) => void
    vi.mocked(listAgents).mockImplementation(
      () => new Promise((resolve) => { resolvePromise = resolve }),
    )

    const promise = useAgentsStore.getState().fetchAgents()
    expect(useAgentsStore.getState().listLoading).toBe(true)

    resolvePromise({ data: [], total: 0, offset: 0, limit: 200 })
    await promise
    expect(useAgentsStore.getState().listLoading).toBe(false)
  })
})

describe('fetchAgentDetail', () => {
  it('fetches agent details in parallel', async () => {
    const agent = makeAgent()
    const perf = makePerformance()
    vi.mocked(getAgent).mockResolvedValue(agent)
    vi.mocked(getAgentPerformance).mockResolvedValue(perf)
    vi.mocked(listTasks).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 50 })
    vi.mocked(getAgentActivity).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 50 })
    vi.mocked(getAgentHistory).mockResolvedValue([])

    await useAgentsStore.getState().fetchAgentDetail('Alice Smith')

    const state = useAgentsStore.getState()
    expect(state.selectedAgent).toEqual(agent)
    expect(state.performance).toEqual(perf)
    expect(state.detailLoading).toBe(false)
    expect(state.detailError).toBeNull()
  })

  it('degrades gracefully when performance fails', async () => {
    const agent = makeAgent()
    vi.mocked(getAgent).mockResolvedValue(agent)
    vi.mocked(getAgentPerformance).mockRejectedValue(new Error('fail'))
    vi.mocked(listTasks).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 50 })
    vi.mocked(getAgentActivity).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 50 })
    vi.mocked(getAgentHistory).mockResolvedValue([])

    await useAgentsStore.getState().fetchAgentDetail('Alice Smith')

    const state = useAgentsStore.getState()
    expect(state.selectedAgent).toEqual(agent)
    expect(state.performance).toBeNull()
    expect(state.detailError).toBeNull()
  })

  it('sets error when agent fetch fails', async () => {
    vi.mocked(getAgent).mockRejectedValue(new Error('Not found'))
    vi.mocked(getAgentPerformance).mockRejectedValue(new Error('fail'))
    vi.mocked(listTasks).mockRejectedValue(new Error('fail'))
    vi.mocked(getAgentActivity).mockRejectedValue(new Error('fail'))
    vi.mocked(getAgentHistory).mockRejectedValue(new Error('fail'))

    await useAgentsStore.getState().fetchAgentDetail('Unknown')

    const state = useAgentsStore.getState()
    expect(state.selectedAgent).toBeNull()
    expect(state.detailError).toBeTruthy()
  })
})

describe('fetchMoreActivity', () => {
  it('appends new activity events', async () => {
    const existingEvents = [
      { event_type: 'task_completed', timestamp: '2026-03-26T12:00:00Z', description: 'Task done', related_ids: {} },
    ]
    useAgentsStore.setState({ activity: existingEvents, activityTotal: 5 })

    const newEvents = [
      { event_type: 'hired', timestamp: '2026-03-25T10:00:00Z', description: 'Agent hired', related_ids: {} },
    ]
    vi.mocked(getAgentActivity).mockResolvedValue({ data: newEvents, total: 5, offset: 1, limit: 20 })

    await useAgentsStore.getState().fetchMoreActivity('Alice Smith', 1)

    expect(useAgentsStore.getState().activity).toHaveLength(2)
  })
})

describe('filter setters', () => {
  it('sets search query', () => {
    useAgentsStore.getState().setSearchQuery('alice')
    expect(useAgentsStore.getState().searchQuery).toBe('alice')
  })

  it('sets department filter', () => {
    useAgentsStore.getState().setDepartmentFilter('engineering')
    expect(useAgentsStore.getState().departmentFilter).toBe('engineering')
  })

  it('sets level filter', () => {
    useAgentsStore.getState().setLevelFilter('senior')
    expect(useAgentsStore.getState().levelFilter).toBe('senior')
  })

  it('sets status filter', () => {
    useAgentsStore.getState().setStatusFilter('active')
    expect(useAgentsStore.getState().statusFilter).toBe('active')
  })

  it('sets sort by', () => {
    useAgentsStore.getState().setSortBy('department')
    expect(useAgentsStore.getState().sortBy).toBe('department')
  })
})

describe('clearDetail', () => {
  it('resets all detail state', () => {
    useAgentsStore.setState({
      selectedAgent: makeAgent(),
      performance: makePerformance(),
      agentTasks: [],
      activity: [],
      activityTotal: 10,
      careerHistory: [],
      detailLoading: true,
      detailError: 'some error',
    })

    useAgentsStore.getState().clearDetail()

    const state = useAgentsStore.getState()
    expect(state.selectedAgent).toBeNull()
    expect(state.performance).toBeNull()
    expect(state.activityTotal).toBe(0)
    expect(state.detailLoading).toBe(false)
    expect(state.detailError).toBeNull()
  })
})
