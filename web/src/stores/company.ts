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
} from '@/api/endpoints/company'
import { getErrorMessage } from '@/utils/errors'
import type {
  AgentConfig,
  CompanyConfig,
  CreateAgentOrgRequest,
  CreateDepartmentRequest,
  Department,
  DepartmentHealth,
  DepartmentName,
  UpdateAgentOrgRequest,
  UpdateCompanyRequest,
  UpdateDepartmentRequest,
  WsEvent,
} from '@/api/types'

interface CompanyState {
  config: CompanyConfig | null
  departmentHealths: readonly DepartmentHealth[]
  loading: boolean
  error: string | null
  healthError: string | null
  savingCount: number
  saveError: string | null

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

  optimisticReorderDepartments: (orderedNames: string[]) => () => void
  optimisticReorderAgents: (deptName: string, orderedIds: string[]) => () => void
  optimisticReassignAgent: (agentName: string, newDepartment: DepartmentName) => () => void
}

export const useCompanyStore = create<CompanyState>()((set, get) => ({
  config: null,
  departmentHealths: [],
  loading: false,
  error: null,
  healthError: null,
  savingCount: 0,
  saveError: null,

  fetchCompanyData: async () => {
    set({ loading: true, error: null })
    try {
      const config = await getCompanyConfig()
      set({ config, loading: false, error: null })
    } catch (err) {
      set({ loading: false, error: getErrorMessage(err) })
      throw err
    }
  },

  fetchDepartmentHealths: async () => {
    try {
      const config = useCompanyStore.getState().config
      if (!config) return
      const healthPromises = config.departments.map((dept) =>
        getDepartmentHealth(dept.name).catch((err: unknown) => {
          console.warn('[CompanyStore] Health fetch failed for dept:', dept.name, err)
          return null
        }),
      )
      const healthResults = await Promise.all(healthPromises)
      const departmentHealths = healthResults.filter(
        (h): h is DepartmentHealth => h !== null,
      )
      if (departmentHealths.length === 0 && config.departments.length > 0) {
        set({ departmentHealths, healthError: 'Failed to fetch department health data' })
      } else {
        set({ departmentHealths, healthError: null })
      }
    } catch (err) {
      set({ healthError: getErrorMessage(err) })
    }
  },

  updateFromWsEvent: (event) => {
    if (event.event_type === 'agent.hired' || event.event_type === 'agent.fired') {
      const store = useCompanyStore.getState()
      store.fetchCompanyData()
        .then(() => store.fetchDepartmentHealths())
        .catch((err: unknown) => {
          // Errors are set in store state by the respective fetch methods;
          // log for observability in case both swallow the error.
          console.error('[CompanyStore] WS refresh failed:', getErrorMessage(err))
        })
    }
  },

  // ── Mutations ──────────────────────────────────────────────

  updateCompany: async (data) => {
    set((s) => ({ savingCount: s.savingCount + 1, saveError: null }))
    try {
      const updated = await apiUpdateCompany(data)
      set((s) => ({ config: updated, savingCount: Math.max(0, s.savingCount - 1) }))
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
      const updated = await apiReorderDepartments({ department_names: orderedNames })
      set((s) => ({ config: updated, savingCount: Math.max(0, s.savingCount - 1) }))
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
      const updatedDept = await apiReorderAgents(deptName, { agent_ids: orderedIds })
      const prev = get().config
      set((s) => ({
        savingCount: Math.max(0, s.savingCount - 1),
        ...(prev ? {
          config: {
            ...prev,
            departments: prev.departments.map((d) =>
              d.name === deptName ? updatedDept : d,
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
    const idSet = new Set(orderedIds)
    const prevDeptAgentIds = prev.agents
      .filter((a) => a.department === deptName && idSet.has(a.id))
      .map((a) => a.id)
    const agentMap = new Map(
      prev.agents
        .filter((a) => a.department === deptName && idSet.has(a.id))
        .map((a) => [a.id, a]),
    )
    // Preserve original array positions: replace in-place instead of appending
    let reorderIdx = 0
    const reorderedList = orderedIds
      .map((id) => agentMap.get(id))
      .filter((a): a is AgentConfig => a !== undefined)
    const agents = prev.agents.map((a) => {
      if (a.department === deptName && idSet.has(a.id)) {
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
          .map((a) => [a.id, a]),
      )
      let restoreIdx = 0
      const restoredOrder = prevDeptAgentIds
        .map((id) => currentAgentMap.get(id))
        .filter((a): a is AgentConfig => a !== undefined)
      const restoredAgents = current.agents.map((a) => {
        if (a.department === deptName && idSet.has(a.id)) {
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
