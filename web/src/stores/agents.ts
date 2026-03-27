import { create } from 'zustand'
import { listAgents, getAgent, getAgentPerformance, getAgentActivity, getAgentHistory } from '@/api/endpoints/agents'
import { listTasks } from '@/api/endpoints/tasks'
import { getErrorMessage } from '@/utils/errors'
import type {
  AgentActivityEvent,
  AgentConfig,
  AgentPerformanceSummary,
  AgentStatus,
  CareerEvent,
  DepartmentName,
  SeniorityLevel,
  Task,
} from '@/api/types'
import type { AgentSortKey } from '@/utils/agents'

const MAX_ACTIVITIES = 100

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
  careerHistory: readonly CareerEvent[]
  detailLoading: boolean
  detailError: string | null

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
}

export const useAgentsStore = create<AgentsState>()((set) => ({
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
  careerHistory: [],
  detailLoading: false,
  detailError: null,

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
      set({ listLoading: false, listError: getErrorMessage(err) })
    }
  },

  fetchAgentDetail: async (name: string) => {
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

      const agent = agentResult.status === 'fulfilled' ? agentResult.value : null
      if (!agent) {
        const reason = agentResult.status === 'rejected' ? agentResult.reason : null
        set({ detailLoading: false, detailError: getErrorMessage(reason ?? 'Agent not found') })
        return
      }

      set({
        selectedAgent: agent,
        performance: perfResult.status === 'fulfilled' ? perfResult.value : null,
        agentTasks: tasksResult.status === 'fulfilled' ? tasksResult.value.data : [],
        activity: activityResult.status === 'fulfilled' ? activityResult.value.data : [],
        activityTotal: activityResult.status === 'fulfilled' ? activityResult.value.total : 0,
        careerHistory: historyResult.status === 'fulfilled' ? historyResult.value : [],
        detailLoading: false,
        detailError: null,
      })
    } catch (err) {
      set({ detailLoading: false, detailError: getErrorMessage(err) })
    }
  },

  fetchMoreActivity: async (name: string, offset: number) => {
    try {
      const result = await getAgentActivity(name, { offset, limit: 20 })
      set((state) => ({
        activity: [...state.activity, ...result.data].slice(0, MAX_ACTIVITIES),
        activityTotal: result.total,
      }))
    } catch {
      // Silent failure for pagination -- existing data remains
    }
  },

  setSearchQuery: (q) => set({ searchQuery: q }),
  setDepartmentFilter: (d) => set({ departmentFilter: d }),
  setLevelFilter: (l) => set({ levelFilter: l }),
  setStatusFilter: (s) => set({ statusFilter: s }),
  setSortBy: (key) => set({ sortBy: key }),
  setSortDirection: (dir) => set({ sortDirection: dir }),

  clearDetail: () =>
    set({
      selectedAgent: null,
      performance: null,
      agentTasks: [],
      activity: [],
      activityTotal: 0,
      careerHistory: [],
      detailLoading: false,
      detailError: null,
    }),
}))
