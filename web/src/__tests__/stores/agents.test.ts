import { useAgentsStore } from '@/stores/agents'
import { useToastStore } from '@/stores/toast'
import type { AgentConfig, AgentPerformanceSummary, Task } from '@/api/types'

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
    memory: { type: 'persistent', retention_days: null },
    tools: { access_level: 'standard', allowed: ['git'], denied: [] },
    authority: {},
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

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-001',
    title: 'Test Task',
    description: 'A test task',
    type: 'development',
    status: 'completed',
    priority: 'medium',
    project: 'test-project',
    created_by: 'system',
    assigned_to: 'Alice Smith',
    reviewers: [],
    dependencies: [],
    artifacts_expected: [],
    acceptance_criteria: [],
    estimated_complexity: 'medium',
    budget_limit: 1.0,
    deadline: null,
    max_retries: 3,
    parent_task_id: null,
    delegation_chain: [],
    task_structure: null,
    coordination_topology: 'centralized',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: undefined,
    ...overrides,
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
    activityLoading: false,
    careerHistory: [],
    detailLoading: false,
    detailError: null,
    runtimeStatuses: {},
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
    expect(state.listError).toBe('Network error')
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
    expect(state.detailError).toBe('Some data failed to load: performance metrics. Displayed data may be incomplete.')
  })

  it('degrades gracefully when tasks and history fail', async () => {
    const agent = makeAgent()
    vi.mocked(getAgent).mockResolvedValue(agent)
    vi.mocked(getAgentPerformance).mockResolvedValue(makePerformance())
    vi.mocked(listTasks).mockRejectedValue(new Error('tasks fail'))
    vi.mocked(getAgentActivity).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 50 })
    vi.mocked(getAgentHistory).mockRejectedValue(new Error('history fail'))

    await useAgentsStore.getState().fetchAgentDetail('Alice Smith')

    const state = useAgentsStore.getState()
    expect(state.selectedAgent).toEqual(agent)
    expect(state.performance).toBeDefined()
    expect(state.agentTasks).toHaveLength(0)
    expect(state.careerHistory).toHaveLength(0)
    expect(state.detailError).toBe('Some data failed to load: task history, career history. Displayed data may be incomplete.')
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
    expect(state.detailError).toBe('Not found')
  })

  it('rejects stale responses when a newer fetch starts', async () => {
    const agentA = makeAgent({ name: 'Alice Smith' })
    const agentB = makeAgent({ name: 'Bob Jones', role: 'Designer' })

    // Control resolution order: A resolves after B
    let resolveA!: (v: AgentConfig) => void
    let resolveB!: (v: AgentConfig) => void
    vi.mocked(getAgent)
      .mockImplementationOnce(() => new Promise((r) => { resolveA = r }))
      .mockImplementationOnce(() => new Promise((r) => { resolveB = r }))
    vi.mocked(getAgentPerformance).mockResolvedValue(makePerformance())
    vi.mocked(listTasks).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 50 })
    vi.mocked(getAgentActivity).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 50 })
    vi.mocked(getAgentHistory).mockResolvedValue([])

    // Start both fetches
    const promiseA = useAgentsStore.getState().fetchAgentDetail('Alice Smith')
    const promiseB = useAgentsStore.getState().fetchAgentDetail('Bob Jones')

    // Resolve B first (newer), then A (stale)
    resolveB(agentB)
    await promiseB

    expect(useAgentsStore.getState().selectedAgent?.name).toBe('Bob Jones')

    // Resolve A (stale) -- should be rejected by staleness guard
    resolveA(agentA)
    await promiseA

    // Store should still show Bob, not Alice
    expect(useAgentsStore.getState().selectedAgent?.name).toBe('Bob Jones')
  })

  it('rejects in-flight responses after clearDetail', async () => {
    let resolveAgent!: (v: AgentConfig) => void
    vi.mocked(getAgent).mockImplementation(() => new Promise((r) => { resolveAgent = r }))
    vi.mocked(getAgentPerformance).mockResolvedValue(makePerformance())
    vi.mocked(listTasks).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 50 })
    vi.mocked(getAgentActivity).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 50 })
    vi.mocked(getAgentHistory).mockResolvedValue([])

    const promise = useAgentsStore.getState().fetchAgentDetail('Alice Smith')

    // Navigate away (clearDetail resets staleness token)
    useAgentsStore.getState().clearDetail()
    expect(useAgentsStore.getState().selectedAgent).toBeNull()

    // Late response arrives -- should be rejected
    resolveAgent(makeAgent())
    await promise

    expect(useAgentsStore.getState().selectedAgent).toBeNull()
    expect(useAgentsStore.getState().detailLoading).toBe(false)
  })
})

describe('fetchMoreActivity', () => {
  it('appends new activity events', async () => {
    const existingEvents = [
      { event_type: 'task_completed', timestamp: '2026-03-26T12:00:00Z', description: 'Task done', related_ids: {} },
    ]
    useAgentsStore.setState({
      activity: existingEvents,
      activityTotal: 1,
      selectedAgent: makeAgent({ name: 'Alice Smith' }),
    })

    const newEvents = [
      { event_type: 'hired', timestamp: '2026-03-25T10:00:00Z', description: 'Agent hired', related_ids: {} },
    ]
    vi.mocked(getAgentActivity).mockResolvedValue({ data: newEvents, total: 5, offset: 1, limit: 20 })

    await useAgentsStore.getState().fetchMoreActivity('Alice Smith', 1)

    expect(useAgentsStore.getState().activity).toHaveLength(2)
    expect(useAgentsStore.getState().activityTotal).toBe(5)
  })

  it('caps activity at MAX_ACTIVITIES (100)', async () => {
    const existingEvents = Array.from({ length: 99 }, (_, i) => ({
      event_type: 'task_completed',
      timestamp: `2026-03-26T${String(i % 24).padStart(2, '0')}:${String(Math.floor(i / 24)).padStart(2, '0')}:00Z`,
      description: `Event ${i}`,
      related_ids: {},
    }))
    useAgentsStore.setState({ activity: existingEvents, activityTotal: 200, selectedAgent: makeAgent({ name: 'Alice Smith' }) })

    const newEvents = Array.from({ length: 5 }, (_, i) => ({
      event_type: 'hired',
      timestamp: `2026-03-25T${String(i % 24).padStart(2, '0')}:00:00Z`,
      description: `New event ${i}`,
      related_ids: {},
    }))
    vi.mocked(getAgentActivity).mockResolvedValue({ data: newEvents, total: 200, offset: 99, limit: 20 })

    await useAgentsStore.getState().fetchMoreActivity('Alice Smith', 99)

    expect(useAgentsStore.getState().activity).toHaveLength(100)
  })

  it('preserves existing data on failure', async () => {
    const existingEvents = [
      { event_type: 'task_completed', timestamp: '2026-03-26T12:00:00Z', description: 'Task done', related_ids: {} },
    ]
    useAgentsStore.setState({ activity: existingEvents, activityTotal: 5, selectedAgent: makeAgent({ name: 'Alice Smith' }) })

    vi.mocked(getAgentActivity).mockRejectedValue(new Error('Network error'))

    await useAgentsStore.getState().fetchMoreActivity('Alice Smith', 1)

    expect(useAgentsStore.getState().activity).toHaveLength(1)
    expect(useAgentsStore.getState().activity[0]!.description).toBe('Task done')
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

  it('sets sort direction', () => {
    useAgentsStore.getState().setSortDirection('desc')
    expect(useAgentsStore.getState().sortDirection).toBe('desc')
  })
})

describe('clearDetail', () => {
  it('resets all detail state', () => {
    useAgentsStore.setState({
      selectedAgent: makeAgent(),
      performance: makePerformance(),
      agentTasks: [makeTask()],
      activity: [{ event_type: 'hired', timestamp: '2026-01-01T00:00:00Z', description: 'Hired', related_ids: {} }],
      activityTotal: 10,
      activityLoading: true,
      careerHistory: [{ event_type: 'hired' as const, timestamp: '2026-01-01T00:00:00Z', description: 'Hired', initiated_by: 'system', metadata: {} }],
      detailLoading: true,
      detailError: 'some error',
    })

    useAgentsStore.getState().clearDetail()

    const state = useAgentsStore.getState()
    expect(state.selectedAgent).toBeNull()
    expect(state.performance).toBeNull()
    expect(state.agentTasks).toHaveLength(0)
    expect(state.activity).toHaveLength(0)
    expect(state.activityTotal).toBe(0)
    expect(state.activityLoading).toBe(false)
    expect(state.careerHistory).toHaveLength(0)
    expect(state.detailLoading).toBe(false)
    expect(state.detailError).toBeNull()
  })
})

describe('runtime statuses (org chart)', () => {
  it('updateRuntimeStatus sets status for an agent', () => {
    useAgentsStore.getState().updateRuntimeStatus('agent-1', 'active')
    expect(useAgentsStore.getState().runtimeStatuses['agent-1']).toBe('active')
  })

  it('updateFromWsEvent updates status on agent.status_changed', () => {
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'agent.status_changed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: { agent_id: 'agent-1', status: 'active' },
    })
    expect(useAgentsStore.getState().runtimeStatuses['agent-1']).toBe('active')
  })

  it('updateFromWsEvent ignores events with missing agent_id', () => {
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'agent.status_changed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: { status: 'active' },
    })
    expect(Object.keys(useAgentsStore.getState().runtimeStatuses)).toHaveLength(0)
  })

  it('updateFromWsEvent ignores events with missing status', () => {
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'agent.status_changed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: { agent_id: 'agent-1' },
    })
    expect(Object.keys(useAgentsStore.getState().runtimeStatuses)).toHaveLength(0)
  })

  it('updateFromWsEvent ignores invalid status values', () => {
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'agent.status_changed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: { agent_id: 'agent-1', status: 'invalid_status' },
    })
    expect(Object.keys(useAgentsStore.getState().runtimeStatuses)).toHaveLength(0)
  })

  it('updateFromWsEvent ignores non-status events', () => {
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'task.created',
      channel: 'tasks',
      timestamp: '2026-03-27T10:00:00Z',
      payload: {},
    })
    expect(Object.keys(useAgentsStore.getState().runtimeStatuses)).toHaveLength(0)
  })
})

describe('personality.trimmed toast dispatch', () => {
  beforeEach(() => {
    useToastStore.getState().dismissAll()
    useAgentsStore.setState({ runtimeStatuses: {} })
  })

  it('does not dispatch a toast for personality.trimmed (handled by notifications pipeline)', () => {
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'personality.trimmed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: {
        agent_id: 'agent-1',
        agent_name: 'Alice',
        task_id: 'task-1',
        before_tokens: 600,
        after_tokens: 120,
        max_tokens: 200,
        trim_tier: 2,
        budget_met: true,
      },
    })

    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('does not dispatch a toast when token fields are missing (handled by notifications pipeline)', () => {
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'personality.trimmed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: { agent_name: 'Bob' },
    })

    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('suppresses the toast when every payload field is missing', () => {
    // Fully-empty payload carries zero actionable info ("An agent personality
    // was trimmed" with no name or numbers), so the store should drop it --
    // the warn log inside updateFromWsEvent retains the diagnostic signal.
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'personality.trimmed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: {},
    })

    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('does not affect runtimeStatuses', () => {
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'personality.trimmed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: { agent_name: 'Alice', before_tokens: 600, after_tokens: 120 },
    })
    expect(Object.keys(useAgentsStore.getState().runtimeStatuses)).toHaveLength(0)
  })

  it('does not dispatch a toast for long agent_name (handled by notifications pipeline)', () => {
    const longName = 'A'.repeat(200)
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'personality.trimmed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: {
        agent_name: longName,
        before_tokens: 600,
        after_tokens: 120,
      },
    })

    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('does not dispatch a toast for non-finite token values (handled by notifications pipeline)', () => {
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'personality.trimmed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: {
        agent_name: 'Carol',
        before_tokens: Number.POSITIVE_INFINITY,
        after_tokens: Number.NaN,
      },
    })

    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('does not dispatch a toast for non-string agent_name (handled by notifications pipeline)', () => {
    useAgentsStore.getState().updateFromWsEvent({
      event_type: 'personality.trimmed',
      channel: 'agents',
      timestamp: '2026-03-27T10:00:00Z',
      payload: {
        agent_name: 12345,
        before_tokens: 600,
        after_tokens: 120,
      },
    })

    expect(useToastStore.getState().toasts).toHaveLength(0)
  })
})
