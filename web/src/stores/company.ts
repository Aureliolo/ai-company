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
        set({ departmentHealths, error: 'Failed to fetch department health data' })
      } else {
        set({ departmentHealths, error: null })
      }
    } catch (err) {
      set({ error: getErrorMessage(err) })
    }
  },

  updateFromWsEvent: (event) => {
    if (event.event_type === 'agent.hired' || event.event_type === 'agent.fired') {
      const store = useCompanyStore.getState()
      store.fetchCompanyData()
        .then(() => store.fetchDepartmentHealths())
        .catch(() => {
          // Errors are set in store state by the respective fetch methods
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
      await apiReorderAgents(deptName, { agent_ids: orderedIds })
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
    const deptMap = new Map(prev.departments.map((d) => [d.name, d]))
    const reordered = orderedNames
      .map((n) => deptMap.get(n as Department['name']))
      .filter((d): d is Department => d !== undefined)
    set({ config: { ...prev, departments: reordered } })
    return () => set({ config: prev })
  },

  optimisticReorderAgents: (deptName, orderedIds) => {
    const prev = get().config
    if (!prev) return () => {}
    const idSet = new Set(orderedIds)
    const deptAgents = prev.agents.filter(
      (a) => a.department === deptName && idSet.has(a.id),
    )
    const agentMap = new Map(deptAgents.map((a) => [a.id, a]))
    const reordered = orderedIds
      .map((id) => agentMap.get(id))
      .filter((a): a is AgentConfig => a !== undefined)
    const otherAgents = prev.agents.filter(
      (a) => a.department !== deptName || !idSet.has(a.id),
    )
    set({ config: { ...prev, agents: [...otherAgents, ...reordered] } })
    return () => set({ config: prev })
  },
}))
