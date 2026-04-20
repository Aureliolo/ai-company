import { create } from 'zustand'
import {
  getCompanyConfig,
  getDepartmentHealth,
  updateCompany as apiUpdateCompany,
  createDepartment as apiCreateDepartment,
  updateDepartment as apiUpdateDepartment,
  deleteDepartment as apiDeleteDepartment,
  reorderDepartments as apiReorderDepartments,
  createAgentOrg as apiCreateAgent,
  updateAgentOrg as apiUpdateAgent,
  deleteAgent as apiDeleteAgent,
  reorderAgents as apiReorderAgents,
  createTeam as apiCreateTeam,
  updateTeam as apiUpdateTeam,
  deleteTeam as apiDeleteTeam,
  reorderTeams as apiReorderTeams,
} from '@/api/endpoints/company'
import { getErrorMessage } from '@/utils/errors'
import { createLogger } from '@/lib/logger'
import type { AgentConfig } from '@/api/types/agents'
import type { DepartmentHealth } from '@/api/types/analytics'
import type { DepartmentName } from '@/api/types/enums'
import type {
  CompanyConfig,
  CreateAgentOrgRequest,
  CreateDepartmentRequest,
  CreateTeamRequest,
  Department,
  TeamConfig,
  UpdateAgentOrgRequest,
  UpdateCompanyRequest,
  UpdateDepartmentRequest,
  UpdateTeamRequest,
} from '@/api/types/org'
import type { WsEvent } from '@/api/types/websocket'

const log = createLogger('company')

interface CompanyState {
  config: CompanyConfig | null
  departmentHealths: readonly DepartmentHealth[]
  loading: boolean
  error: string | null
  healthError: string | null
  savingCount: number
  saveError: string | null
  _refreshVersion: number
  _healthRefreshVersion: number

  fetchCompanyData: () => Promise<void>
  fetchDepartmentHealths: () => Promise<void>
  updateFromWsEvent: (event: WsEvent) => void

  updateCompany: (data: UpdateCompanyRequest) => Promise<void>
  createDepartment: (data: CreateDepartmentRequest) => Promise<Department>
  updateDepartment: (name: string, data: UpdateDepartmentRequest) => Promise<Department>
  deleteDepartment: (name: string) => Promise<void>
  reorderDepartments: (orderedNames: string[]) => Promise<void>
  createAgent: (data: CreateAgentOrgRequest) => Promise<AgentConfig>
  updateAgent: (name: string, data: UpdateAgentOrgRequest) => Promise<AgentConfig>
  deleteAgent: (name: string) => Promise<void>
  reorderAgents: (deptName: string, orderedIds: string[]) => Promise<void>

  createTeam: (deptName: string, data: CreateTeamRequest) => Promise<TeamConfig>
  updateTeam: (deptName: string, teamName: string, data: UpdateTeamRequest) => Promise<TeamConfig>
  deleteTeam: (deptName: string, teamName: string, reassignTo?: string) => Promise<void>
  reorderTeams: (deptName: string, orderedNames: string[]) => Promise<void>

  optimisticReorderDepartments: (orderedNames: string[]) => () => void
  optimisticReorderAgents: (deptName: string, orderedIds: string[]) => () => void
  optimisticReassignAgent: (agentName: string, newDepartment: DepartmentName) => () => void
}

const ORG_MUTATION_EVENTS: ReadonlySet<string> = new Set([
  'agent.hired', 'agent.fired',
  'company.updated',
  'department.created', 'department.updated', 'department.deleted', 'departments.reordered',
  'agent.created', 'agent.updated', 'agent.deleted', 'agents.reordered',
])

export const useCompanyStore = create<CompanyState>()((set, get) => ({
  config: null,
  departmentHealths: [],
  loading: false,
  error: null,
  healthError: null,
  savingCount: 0,
  saveError: null,
  _refreshVersion: 0,
  _healthRefreshVersion: 0,

  fetchCompanyData: async () => {
    const version = get()._refreshVersion + 1
    set({ _refreshVersion: version, loading: true, error: null })
    try {
      const config = await getCompanyConfig()
      if (get()._refreshVersion !== version) return // stale response
      set({ config, loading: false, error: null })
    } catch (err) {
      if (get()._refreshVersion !== version) return // stale error
      set({ loading: false, error: getErrorMessage(err) })
      throw err
    }
  },

  fetchDepartmentHealths: async () => {
    const version = get()._healthRefreshVersion + 1
    set({ _healthRefreshVersion: version })
    try {
      const config = useCompanyStore.getState().config
      if (!config) return
      const healthPromises = config.departments.map((dept) =>
        getDepartmentHealth(dept.name).catch((err: unknown) => {
          log.warn('Health fetch failed for dept:', dept.name, err)
          return null
        }),
      )
      const healthResults = await Promise.all(healthPromises)
      if (get()._healthRefreshVersion !== version) return // stale response
      const departmentHealths = healthResults.filter(
        (h): h is DepartmentHealth => h !== null,
      )
      if (departmentHealths.length === 0 && config.departments.length > 0) {
        set({ departmentHealths, healthError: 'Failed to fetch department health data' })
      } else {
        set({ departmentHealths, healthError: null })
      }
    } catch (err) {
      if (get()._healthRefreshVersion !== version) return // stale error
      set({ healthError: getErrorMessage(err) })
    }
  },

  updateFromWsEvent: (event) => {
    if (ORG_MUTATION_EVENTS.has(event.event_type)) {
      const store = useCompanyStore.getState()
      store.fetchCompanyData()
        .then(() => store.fetchDepartmentHealths())
        .catch((err: unknown) => {
          // Errors are set in store state by the respective fetch methods;
          // log for observability in case both swallow the error.
          log.error('WS refresh failed:', getErrorMessage(err))
        })
    }
  },

  // ── Mutations ──────────────────────────────────────────────

  updateCompany: async (data) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      await apiUpdateCompany(data)
      // Refetch full config to reflect partial-update response
      await get().fetchCompanyData()
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1) }))
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  createDepartment: async (data) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      const dept = await apiCreateDepartment(data)
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? { config: { ...prev, departments: [...prev.departments, dept] } } : {}),
      }))
      return dept
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  updateDepartment: async (name, data) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      const dept = await apiUpdateDepartment(name, data)
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? { config: { ...prev, departments: prev.departments.map((d) => (d.name === name ? dept : d)) } } : {}),
      }))
      return dept
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  deleteDepartment: async (name) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      await apiDeleteDepartment(name)
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? { config: { ...prev, departments: prev.departments.filter((d) => d.name !== name) } } : {}),
      }))
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  reorderDepartments: async (orderedNames) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      const reordered = await apiReorderDepartments({ department_names: orderedNames })
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? { config: { ...prev, departments: [...reordered] } } : {}),
      }))
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  createAgent: async (data) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      const agent = await apiCreateAgent(data)
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? { config: { ...prev, agents: [...prev.agents, agent] } } : {}),
      }))
      return agent
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  updateAgent: async (name, data) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      const agent = await apiUpdateAgent(name, data)
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? { config: { ...prev, agents: prev.agents.map((a) => (a.name === name ? agent : a)) } } : {}),
      }))
      return agent
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  deleteAgent: async (name) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      await apiDeleteAgent(name)
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? { config: { ...prev, agents: prev.agents.filter((a) => a.name !== name) } } : {}),
      }))
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  reorderAgents: async (deptName, orderedIds) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      // Callers pass `a.id ?? a.name` as identifiers, but the API
      // expects agent names.  Resolve each id back to its name so the
      // payload is always correct even when id differs from name.
      const prev = get().config
      const idToName = new Map(
        (prev?.agents ?? []).map((a) => [a.id ?? a.name, a.name]),
      )
      const orderedNames = orderedIds.map((id) => idToName.get(id) ?? id)
      await apiReorderAgents(deptName, { agent_names: orderedNames })
      // Refetch to pick up the reordered agents consistently
      await get().fetchCompanyData()
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
      }))
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  // ── Team mutations ────────────────────────────────────────

  createTeam: async (deptName, data) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      const team = await apiCreateTeam(deptName, data)
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? {
          config: {
            ...prev,
            departments: prev.departments.map((d) =>
              d.name === deptName ? { ...d, teams: [...d.teams, team] } : d,
            ),
          },
        } : {}),
      }))
      return team
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  updateTeam: async (deptName, teamName, data) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      const team = await apiUpdateTeam(deptName, teamName, data)
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? {
          config: {
            ...prev,
            departments: prev.departments.map((d) =>
              d.name === deptName
                ? { ...d, teams: d.teams.map((t) => (t.name === teamName ? team : t)) }
                : d,
            ),
          },
        } : {}),
      }))
      return team
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  deleteTeam: async (deptName, teamName, reassignTo) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      await apiDeleteTeam(deptName, teamName, reassignTo)
      if (reassignTo) {
        await get().fetchCompanyData()
        set((s) => ({ savingCount: Math.max(0, s.savingCount - 1) }))
      } else {
        const prev = get().config
        set((s) => ({
          savingCount: Math.max(0, s.savingCount - 1),
          ...(prev ? {
            config: {
              ...prev,
              departments: prev.departments.map((d) =>
                d.name === deptName
                  ? { ...d, teams: d.teams.filter((t) => t.name !== teamName) }
                  : d,
              ),
            },
          } : {}),
        }))
      }
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  reorderTeams: async (deptName, orderedNames) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      const reordered = await apiReorderTeams(deptName, { team_names: orderedNames })
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? {
          config: {
            ...prev,
            departments: prev.departments.map((d) =>
              d.name === deptName ? { ...d, teams: reordered } : d,
            ),
          },
        } : {}),
      }))
    } catch (err) {
      set((s) => ({ savingCount: Math.max(0, s.savingCount - 1), saveError: getErrorMessage(err) }))
      throw err
    }
  },

  // ── Optimistic helpers ─────────────────────────────────────

  optimisticReorderDepartments: (orderedNames) => {
    const prev = get().config
    if (!prev) return () => {}
    const prevOrder = prev.departments.map((d) => d.name)
    const deptMap = new Map(prev.departments.map((d) => [d.name, d]))
    const reordered = orderedNames
      .map((n) => deptMap.get(n as Department['name']))
      .filter((d): d is Department => d !== undefined)
    set({ config: { ...prev, departments: reordered } })
    // Targeted rollback: restore only department ordering, not entire config
    return () => {
      const current = get().config
      if (!current) return
      const currentMap = new Map(current.departments.map((d) => [d.name, d]))
      const prevSet = new Set(prevOrder)
      // Restore previous ordering, then append any departments added concurrently
      const restored = prevOrder
        .map((n) => currentMap.get(n as Department['name']))
        .filter((d): d is Department => d !== undefined)
      const added = current.departments.filter((d) => !prevSet.has(d.name))
      set({ config: { ...current, departments: [...restored, ...added] } })
    }
  },

  optimisticReorderAgents: (deptName, orderedIds) => {
    const prev = get().config
    if (!prev) return () => {}
    const idOf = (a: AgentConfig) => a.id ?? a.name
    const idSet = new Set(orderedIds)
    const prevDeptAgentIds = prev.agents
      .filter((a) => a.department === deptName && idSet.has(idOf(a)))
      .map(idOf)
    const agentMap = new Map(
      prev.agents
        .filter((a) => a.department === deptName && idSet.has(idOf(a)))
        .map((a) => [idOf(a), a]),
    )
    // Preserve original array positions: replace in-place instead of appending
    let reorderIdx = 0
    const reorderedList = orderedIds
      .map((id) => agentMap.get(id))
      .filter((a): a is AgentConfig => a !== undefined)
    const agents = prev.agents.map((a) => {
      if (a.department === deptName && idSet.has(idOf(a))) {
        return reorderedList[reorderIdx++] ?? a
      }
      return a
    })
    set({ config: { ...prev, agents } })
    // Targeted rollback: restore only this department's agent ordering
    return () => {
      const current = get().config
      if (!current) return
      const currentAgentMap = new Map(
        current.agents
          .filter((a) => a.department === deptName)
          .map((a) => [idOf(a), a]),
      )
      let restoreIdx = 0
      const restoredOrder = prevDeptAgentIds
        .map((id) => currentAgentMap.get(id))
        .filter((a): a is AgentConfig => a !== undefined)
      const restoredAgents = current.agents.map((a) => {
        if (a.department === deptName && idSet.has(idOf(a))) {
          return restoredOrder[restoreIdx++] ?? a
        }
        return a
      })
      set({ config: { ...current, agents: restoredAgents } })
    }
  },

  optimisticReassignAgent: (agentName, newDepartment) => {
    const prev = get().config
    if (!prev) return () => {}
    const agent = prev.agents.find((a) => a.name === agentName)
    if (!agent || agent.department === newDepartment) return () => {}
    const prevDepartment = agent.department
    const agents = prev.agents.map((a) =>
      a.name === agentName ? { ...a, department: newDepartment } : a,
    )
    set({ config: { ...prev, agents } })
    // Targeted rollback: restore only this agent's department if still on the optimistic value
    return () => {
      const current = get().config
      if (!current) return
      const currentAgent = current.agents.find((a) => a.name === agentName)
      // Only rollback if this exact optimistic change is still the active one
      if (!currentAgent || currentAgent.department !== newDepartment) return
      const currentAgents = current.agents.map((a) =>
        a.name === agentName ? { ...a, department: prevDepartment } : a,
      )
      set({ config: { ...current, agents: currentAgents } })
    }
  },
}))
