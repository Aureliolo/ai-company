import { create } from 'zustand'
import { getCompanyConfig, listDepartments, getDepartmentHealth } from '@/api/endpoints/company'
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
      const deptResult = await listDepartments({ limit: 100 })
      const healthPromises = deptResult.data.map((dept) =>
        getDepartmentHealth(dept.name).catch((err: unknown) => {
          console.warn(`Failed to fetch health for ${dept.name}:`, err)
          return null
        }),
      )
      const healthResults = await Promise.all(healthPromises)
      const departmentHealths = healthResults.filter(
        (h): h is DepartmentHealth => h !== null,
      )
      set({ departmentHealths })
    } catch (err) {
      console.warn('Failed to fetch department health:', err)
    }
  },

  updateFromWsEvent: (event) => {
    // Handle system events that affect company structure
    if (event.event_type === 'agent.hired' || event.event_type === 'agent.fired') {
      // Re-fetch company config to get updated agent list
      useCompanyStore.getState().fetchCompanyData()
    }
  },
}))
