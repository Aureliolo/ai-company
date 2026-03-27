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
  saving: boolean
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
}

export const useCompanyStore = create<CompanyState>()((set, get) => ({
  config: null,
  departmentHealths: [],
  loading: false,
  error: null,
  healthError: null,
  saving: false,
  saveError: null,

  fetchCompanyData: async () => {
    set({ loading: true, error: null })
    try {
      const config = await getCompanyConfig()
      set({ config, loading: false, error: null })
    } catch (err) {
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  fetchDepartmentHealths: async () => {
    try {
      const config = useCompanyStore.getState().config
      if (!config) return
      const healthPromises = config.departments.map((dept) =>
        getDepartmentHealth(dept.name).catch(() => null),
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
          console.error('[CompanyStore] WS refresh failed:', err)
        })
    }
  },

  // ── Mutations ──────────────────────────────────────────────

  updateCompany: async (data) => {
    set({ saving: true, saveError: null })
    try {
      const updated = await apiUpdateCompany(data)
      set({ config: updated, saving: false })
    } catch (err) {
      set({ saving: false, saveError: getErrorMessage(err) })
      throw err
    }
  },

  createDepartment: async (data) => {
    set({ saving: true, saveError: null })
    try {
      const dept = await apiCreateDepartment(data)
      const prev = get().config
      if (prev) {
        set({ config: { ...prev, departments: [...prev.departments, dept] } })
      }
      set({ saving: false })
      return dept
    } catch (err) {
      set({ saving: false, saveError: getErrorMessage(err) })
      throw err
    }
  },

  updateDepartment: async (name, data) => {
    set({ saving: true, saveError: null })
    try {
      const dept = await apiUpdateDepartment(name, data)
      const prev = get().config
      if (prev) {
        set({
          config: {
            ...prev,
            departments: prev.departments.map((d) => (d.name === name ? dept : d)),
          },
        })
      }
      set({ saving: false })
      return dept
    } catch (err) {
      set({ saving: false, saveError: getErrorMessage(err) })
      throw err
    }
  },

  deleteDepartment: async (name) => {
    set({ saving: true, saveError: null })
    try {
      await apiDeleteDepartment(name)
      const prev = get().config
      if (prev) {
        set({
          config: {
            ...prev,
            departments: prev.departments.filter((d) => d.name !== name),
          },
        })
      }
      set({ saving: false })
    } catch (err) {
      set({ saving: false, saveError: getErrorMessage(err) })
      throw err
    }
  },

  reorderDepartments: async (orderedNames) => {
    set({ saving: true, saveError: null })
    try {
      const updated = await apiReorderDepartments({ department_names: orderedNames })
      set({ config: updated, saving: false })
    } catch (err) {
      set({ saving: false, saveError: getErrorMessage(err) })
      throw err
    }
  },

  createAgent: async (data) => {
    set({ saving: true, saveError: null })
    try {
      const agent = await apiCreateAgent(data)
      const prev = get().config
      if (prev) {
        set({ config: { ...prev, agents: [...prev.agents, agent] } })
      }
      set({ saving: false })
      return agent
    } catch (err) {
      set({ saving: false, saveError: getErrorMessage(err) })
      throw err
    }
  },

  updateAgent: async (name, data) => {
    set({ saving: true, saveError: null })
    try {
      const agent = await apiUpdateAgent(name, data)
      const prev = get().config
      if (prev) {
        set({
          config: {
            ...prev,
            agents: prev.agents.map((a) => (a.name === name ? agent : a)),
          },
        })
      }
      set({ saving: false })
      return agent
    } catch (err) {
      set({ saving: false, saveError: getErrorMessage(err) })
      throw err
    }
  },

  deleteAgent: async (name) => {
    set({ saving: true, saveError: null })
    try {
      await apiDeleteAgent(name)
      const prev = get().config
      if (prev) {
        set({
          config: {
            ...prev,
            agents: prev.agents.filter((a) => a.name !== name),
          },
        })
      }
      set({ saving: false })
    } catch (err) {
      set({ saving: false, saveError: getErrorMessage(err) })
      throw err
    }
  },

  reorderAgents: async (deptName, orderedIds) => {
    set({ saving: true, saveError: null })
    try {
      const updatedDept = await apiReorderAgents(deptName, { agent_ids: orderedIds })
      const prev = get().config
      if (prev) {
        set({
          config: {
            ...prev,
            departments: prev.departments.map((d) =>
              d.name === deptName ? updatedDept : d,
            ),
          },
        })
      }
      set({ saving: false })
    } catch (err) {
      set({ saving: false, saveError: getErrorMessage(err) })
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
}))
