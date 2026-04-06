import { create } from 'zustand'
import { listAgents, getAgent, getAgentPerformance, getAgentActivity, getAgentHistory } from '@/api/endpoints/agents'
import { listTasks } from '@/api/endpoints/tasks'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import { createLogger } from '@/lib/logger'
import type {
  AgentActivityEvent,
  AgentConfig,
  AgentPerformanceSummary,
  AgentStatus,
  CareerEvent,
  DepartmentName,
  SeniorityLevel,
  Task,
  WsEvent,
} from '@/api/types'
import type { AgentRuntimeStatus } from '@/lib/utils'
import type { AgentSortKey } from '@/utils/agents'

const log = createLogger('agents')

const MAX_ACTIVITIES = 100

const VALID_RUNTIME_STATUSES: ReadonlySet<string> = new Set([
  'active', 'idle', 'error', 'offline',
])

interface AgentsState {
  // List page
  agents: readonly AgentConfig[]
  totalAgents: number
  listLoading: boolean
  listError: string | null

  // Filters
  searchQuery: string
  departmentFilter: DepartmentName | null
  levelFilter: SeniorityLevel | null
  statusFilter: AgentStatus | null
  sortBy: AgentSortKey
  sortDirection: 'asc' | 'desc'

  // Detail page
  selectedAgent: AgentConfig | null
  performance: AgentPerformanceSummary | null
  agentTasks: readonly Task[]
  activity: readonly AgentActivityEvent[]
  activityTotal: number
  activityLoading: boolean
  careerHistory: readonly CareerEvent[]
  detailLoading: boolean
  detailError: string | null

  // Runtime statuses (org chart real-time)
  runtimeStatuses: Record<string, AgentRuntimeStatus>

  // Actions
  fetchAgents: () => Promise<void>
  fetchAgentDetail: (name: string) => Promise<void>
  fetchMoreActivity: (name: string, offset: number) => Promise<void>
  setSearchQuery: (q: string) => void
  setDepartmentFilter: (d: DepartmentName | null) => void
  setLevelFilter: (l: SeniorityLevel | null) => void
  setStatusFilter: (s: AgentStatus | null) => void
  setSortBy: (key: AgentSortKey) => void
  setSortDirection: (dir: 'asc' | 'desc') => void
  clearDetail: () => void
  updateRuntimeStatus: (agentId: string, status: AgentRuntimeStatus) => void
  updateFromWsEvent: (event: WsEvent) => void
}

// Track the latest requested agent name to prevent stale responses from overwriting
let _detailRequestName = ''

export const useAgentsStore = create<AgentsState>()((set, get) => ({
  // List page defaults
  agents: [],
  totalAgents: 0,
  listLoading: false,
  listError: null,

  // Filter defaults
  searchQuery: '',
  departmentFilter: null,
  levelFilter: null,
  statusFilter: null,
  sortBy: 'name',
  sortDirection: 'asc',

  // Detail page defaults
  selectedAgent: null,
  performance: null,
  agentTasks: [],
  activity: [],
  activityTotal: 0,
  activityLoading: false,
  careerHistory: [],
  detailLoading: false,
  detailError: null,

  // Runtime statuses
  runtimeStatuses: {},

  fetchAgents: async () => {
    set({ listLoading: true, listError: null })
    try {
      const result = await listAgents({ limit: 200 })
      set({
        agents: result.data,
        totalAgents: result.total,
        listLoading: false,
      })
    } catch (err) {
      log.warn('Failed to load agents', err)
      set({ listLoading: false, listError: getErrorMessage(err) })
    }
  },

  fetchAgentDetail: async (name: string) => {
    _detailRequestName = name
    set({ detailLoading: true, detailError: null })
    try {
      const [agentResult, perfResult, tasksResult, activityResult, historyResult] =
        await Promise.allSettled([
          getAgent(name),
          getAgentPerformance(name),
          listTasks({ assigned_to: name, limit: 50 }),
          getAgentActivity(name, { limit: 20 }),
          getAgentHistory(name),
        ])

      // Guard against stale responses from rapid navigation
      if (_detailRequestName !== name) return

      const agent = agentResult.status === 'fulfilled' ? agentResult.value : null
      if (!agent) {
        const reason = agentResult.status === 'rejected' ? agentResult.reason : null
        set({ detailLoading: false, detailError: getErrorMessage(reason ?? 'Agent not found') })
        return
      }

      // Collect partial failure warnings for secondary endpoints
      const partialErrors: string[] = []
      if (perfResult.status === 'rejected') partialErrors.push('performance metrics')
      if (tasksResult.status === 'rejected') partialErrors.push('task history')
      if (activityResult.status === 'rejected') partialErrors.push('activity')
      if (historyResult.status === 'rejected') partialErrors.push('career history')

      set({
        selectedAgent: agent,
        performance: perfResult.status === 'fulfilled' ? perfResult.value : null,
        agentTasks: tasksResult.status === 'fulfilled' ? tasksResult.value.data : [],
        activity: activityResult.status === 'fulfilled' ? activityResult.value.data : [],
        activityTotal: activityResult.status === 'fulfilled' ? activityResult.value.total : 0,
        careerHistory: historyResult.status === 'fulfilled' ? historyResult.value : [],
        detailLoading: false,
        detailError: partialErrors.length > 0
          ? `Some data failed to load: ${partialErrors.join(', ')}. Displayed data may be incomplete.`
          : null,
      })
    } catch (err) {
      if (_detailRequestName !== name) return
      // `name` originates from a URL segment / router param and is therefore
      // attacker-controlled; sanitize before embedding in the structured log.
      log.warn('Failed to load agent detail', { agent: sanitizeForLog(name) }, err)
      set({ detailLoading: false, detailError: getErrorMessage(err) })
    }
  },

  fetchMoreActivity: async (name: string, offset: number) => {
    const { activity, selectedAgent, activityLoading } = get()
    // Short-circuit if already fetching, at client cap, or agent changed
    if (activityLoading) return
    if (activity.length >= MAX_ACTIVITIES) return
    if (selectedAgent && selectedAgent.name !== name) return

    set({ activityLoading: true })
    try {
      const result = await getAgentActivity(name, { offset, limit: 20 })
      // Ignore response if agent changed while fetching
      if (get().selectedAgent?.name !== name) {
        set({ activityLoading: false })
        return
      }
      set((state) => {
        const merged = [...state.activity, ...result.data].slice(0, MAX_ACTIVITIES)
        return {
          activity: merged,
          activityTotal: Math.min(result.total, MAX_ACTIVITIES),
          activityLoading: false,
        }
      })
    } catch (err) {
      // Pagination failure -- existing data preserved, log for debugging
      set({ activityLoading: false })
      log.warn('Failed to load more activity:', getErrorMessage(err))
    }
  },

  setSearchQuery: (q) => set({ searchQuery: q }),
  setDepartmentFilter: (d) => set({ departmentFilter: d }),
  setLevelFilter: (l) => set({ levelFilter: l }),
  setStatusFilter: (s) => set({ statusFilter: s }),
  setSortBy: (key) => set({ sortBy: key }),
  setSortDirection: (dir) => set({ sortDirection: dir }),

  clearDetail: () => {
    // Invalidate any in-flight fetchAgentDetail responses
    _detailRequestName = ''
    set({
      selectedAgent: null,
      performance: null,
      agentTasks: [],
      activity: [],
      activityTotal: 0,
      activityLoading: false,
      careerHistory: [],
      detailLoading: false,
      detailError: null,
    })
  },

  updateRuntimeStatus: (agentId, status) => {
    set((state) => ({
      runtimeStatuses: { ...state.runtimeStatuses, [agentId]: status },
    }))
  },

  updateFromWsEvent: (event) => {
    // Runtime null-guard: `event.payload` is typed as `Record<string, unknown>`
    // on the wire, but a malformed broker could still send `null` or a
    // non-object.  The `as` cast below would not catch that, so we filter
    // here once and treat every invalid envelope as a dropped event.
    if (typeof event.payload !== 'object' || event.payload === null) {
      log.warn('WS event dropped: payload is not an object', {
        event_type: sanitizeForLog(event.event_type),
      })
      return
    }
    if (event.event_type === 'agent.status_changed') {
      const payload = event.payload as Record<string, unknown>
      const agentId = payload.agent_id
      const status = payload.status
      if (typeof agentId !== 'string' || !agentId.trim() || typeof status !== 'string' || !status.trim()) {
        log.warn('agent.status_changed payload missing required fields', {
          hasAgentId: typeof agentId === 'string',
          hasStatus: typeof status === 'string',
        })
        return
      }
      if (!VALID_RUNTIME_STATUSES.has(status)) {
        // `status` arrives from an untrusted WebSocket payload, so sanitize
        // before embedding in the structured log.
        log.warn('agent.status_changed received unknown status', {
          status: sanitizeForLog(status),
          knownStatuses: [...VALID_RUNTIME_STATUSES],
        })
        return
      }
      set((state) => ({
        runtimeStatuses: {
          ...state.runtimeStatuses,
          [agentId]: status as AgentRuntimeStatus,
        },
      }))
      return
    }
    if (event.event_type === 'personality.trimmed') {
      const payload = event.payload as Record<string, unknown>
      const agentNameRaw = payload.agent_name
      const beforeRaw = payload.before_tokens
      const afterRaw = payload.after_tokens

      const agentName =
        typeof agentNameRaw === 'string'
          // Length-bound defence-in-depth: the backend payload is trusted but
          // bounding the visual blast radius of a malformed or oversized
          // agent_name is cheap insurance. React escapes text content, so
          // there is no XSS risk -- this is purely display hygiene.
          ? agentNameRaw.slice(0, 64)
          : null
      // Token counts must be non-negative integers -- reject anything else
      // so a malformed payload (negative, fractional, Infinity, NaN) falls
      // through to the generic fallback description instead of rendering
      // nonsense like "-1 -> 3.14 tokens".
      const isTokenCount = (v: unknown): v is number =>
        typeof v === 'number' && Number.isInteger(v) && v >= 0
      const beforeValid = isTokenCount(beforeRaw) ? beforeRaw : null
      const afterValid = isTokenCount(afterRaw) ? afterRaw : null
      // Monotonicity: trimming must reduce token count.  A payload where
      // after_tokens > before_tokens is contradictory (we would be
      // "trimming" to a larger size), so fall through to the generic
      // fallback copy instead of rendering the swapped numbers.
      const monotonic =
        beforeValid !== null && afterValid !== null
          ? afterValid < beforeValid
          : true
      const before = monotonic ? beforeValid : null
      const after = monotonic ? afterValid : null

      if (agentName === null || before === null || after === null) {
        log.warn('personality.trimmed payload has missing/invalid fields', {
          hasAgentName: agentName !== null,
          hasBeforeTokens: before !== null,
          hasAfterTokens: after !== null,
        })
      }

      // If every field is missing or invalid the toast would carry zero
      // actionable information ("An agent personality was trimmed" with no
      // name or numbers), so suppress it entirely. The warn log above is
      // retained as the diagnostic signal for the dropped event.
      if (agentName === null && before === null && after === null) {
        return
      }

      const displayName = agentName ?? 'An agent'
      const description =
        before !== null && after !== null
          ? `${displayName} personality trimmed: ${before} → ${after} tokens`
          : `${displayName} personality was trimmed to fit token budget`
      useToastStore.getState().add({
        variant: 'info',
        title: 'Personality trimmed',
        description,
      })
      return
    }

    log.debug('WS event ignored: unhandled event_type', { event_type: sanitizeForLog(event?.event_type) })
  },
}))
