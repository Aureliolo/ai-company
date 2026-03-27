import { useCallback, useEffect, useMemo } from 'react'
import { useCompanyStore } from '@/stores/company'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { usePolling } from '@/hooks/usePolling'
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
  WsChannel,
} from '@/api/types'

const ORG_EDIT_POLL_INTERVAL = 30_000
const ORG_EDIT_CHANNELS = ['agents'] as const satisfies readonly WsChannel[]

export interface UseOrgEditDataReturn {
  config: CompanyConfig | null
  departmentHealths: readonly DepartmentHealth[]
  loading: boolean
  error: string | null
  saving: boolean
  saveError: string | null
  wsConnected: boolean
  wsSetupError: string | null

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

export function useOrgEditData(): UseOrgEditDataReturn {
  const config = useCompanyStore((s) => s.config)
  const departmentHealths = useCompanyStore((s) => s.departmentHealths)
  const loading = useCompanyStore((s) => s.loading)
  const error = useCompanyStore((s) => s.error)
  const saving = useCompanyStore((s) => s.savingCount > 0)
  const saveError = useCompanyStore((s) => s.saveError)

  // Mutations (stable references via store actions)
  const updateCompany = useCompanyStore((s) => s.updateCompany)
  const createDepartment = useCompanyStore((s) => s.createDepartment)
  const updateDepartment = useCompanyStore((s) => s.updateDepartment)
  const deleteDepartment = useCompanyStore((s) => s.deleteDepartment)
  const reorderDepartments = useCompanyStore((s) => s.reorderDepartments)
  const createAgent = useCompanyStore((s) => s.createAgent)
  const updateAgent = useCompanyStore((s) => s.updateAgent)
  const deleteAgent = useCompanyStore((s) => s.deleteAgent)
  const reorderAgents = useCompanyStore((s) => s.reorderAgents)
  const optimisticReorderDepartments = useCompanyStore((s) => s.optimisticReorderDepartments)
  const optimisticReorderAgents = useCompanyStore((s) => s.optimisticReorderAgents)

  // Polling for department health refresh
  const pollFn = useCallback(async () => {
    await useCompanyStore.getState().fetchDepartmentHealths()
  }, [])
  const polling = usePolling(pollFn, ORG_EDIT_POLL_INTERVAL)

  // Initial data fetch (sequential: health depends on config)
  useEffect(() => {
    const store = useCompanyStore.getState()
    store.fetchCompanyData().then(() => {
      if (useCompanyStore.getState().config) {
        store.fetchDepartmentHealths()
      }
      polling.start()
    })
    return () => polling.stop()
    // eslint-disable-next-line @eslint-react/exhaustive-deps -- mount-only effect; polling ref identity is stable
  }, [])

  // WebSocket bindings for real-time updates
  const bindings: ChannelBinding[] = useMemo(
    () =>
      ORG_EDIT_CHANNELS.map((channel) => ({
        channel,
        handler: (event) => {
          useCompanyStore.getState().updateFromWsEvent(event)
        },
      })),
    [],
  )

  const { connected: wsConnected, setupError: wsSetupError } = useWebSocket({
    bindings,
  })

  return {
    config,
    departmentHealths,
    loading,
    error,
    saving,
    saveError,
    wsConnected,
    wsSetupError,
    updateCompany,
    createDepartment,
    updateDepartment,
    deleteDepartment,
    reorderDepartments,
    createAgent,
    updateAgent,
    deleteAgent,
    reorderAgents,
    optimisticReorderDepartments,
    optimisticReorderAgents,
  }
}
