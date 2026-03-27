import { create } from 'zustand'
import { getCompanyConfig, getDepartmentHealth } from '@/api/endpoints/company'
import { getErrorMessage } from '@/utils/errors'
import type { CompanyConfig, DepartmentHealth, WsEvent } from '@/api/types'

interface CompanyState {
  config: CompanyConfig | null
  departmentHealths: readonly DepartmentHealth[]
  loading: boolean
  error: string | null
  fetchCompanyData: () => Promise<void>
  fetchDepartmentHealths: () => Promise<void>
  updateFromWsEvent: (event: WsEvent) => void
}

export const useCompanyStore = create<CompanyState>()((set) => ({
  config: null,
  departmentHealths: [],
  loading: false,
  error: null,

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
    // Handle agent lifecycle events that affect company structure
    if (event.event_type === 'agent.hired' || event.event_type === 'agent.fired') {
      // Re-fetch company config to get updated agent list
      const store = useCompanyStore.getState()
      store.fetchCompanyData()
        .then(() => store.fetchDepartmentHealths())
        .catch(() => {
          // Errors are set in store state by the respective fetch methods
        })
    }
  },
}))
