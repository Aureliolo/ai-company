import { useCallback, useEffect, useMemo } from 'react'
import type { Node, Edge } from '@xyflow/react'
import { useCompanyStore } from '@/stores/company'
import { useAgentsStore } from '@/stores/agents'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { usePolling } from '@/hooks/usePolling'
import { buildOrgTree } from '@/pages/org/build-org-tree'
import { applyDagreLayout } from '@/pages/org/layout'
import type { WsChannel } from '@/api/types'

const ORG_POLL_INTERVAL = 30_000
const ORG_CHANNELS = ['agents'] as const satisfies readonly WsChannel[]

export interface UseOrgChartDataReturn {
  nodes: Node[]
  edges: Edge[]
  loading: boolean
  error: string | null
  wsConnected: boolean
  wsSetupError: string | null
}

export function useOrgChartData(): UseOrgChartDataReturn {
  const config = useCompanyStore((s) => s.config)
  const departmentHealths = useCompanyStore((s) => s.departmentHealths)
  const loading = useCompanyStore((s) => s.loading)
  const error = useCompanyStore((s) => s.error)
  const runtimeStatuses = useAgentsStore((s) => s.runtimeStatuses)

  // Polling for department health refresh
  const pollFn = useCallback(async () => {
    await useCompanyStore.getState().fetchDepartmentHealths()
  }, [])
  const polling = usePolling(pollFn, ORG_POLL_INTERVAL)

  // Initial data fetch (sequential: health depends on config being loaded)
  // Polling starts only after initial fetch completes to avoid racing
  useEffect(() => {
    const companyStore = useCompanyStore.getState()
    companyStore.fetchCompanyData().then(() => {
      if (useCompanyStore.getState().config) {
        companyStore.fetchDepartmentHealths()
      }
      polling.start()
    })
    return () => polling.stop()
    // eslint-disable-next-line @eslint-react/exhaustive-deps -- mount-only effect; polling ref identity is stable
  }, [])

  // WebSocket bindings for real-time updates
  const bindings: ChannelBinding[] = useMemo(
    () =>
      ORG_CHANNELS.map((channel) => ({
        channel,
        handler: (event) => {
          useCompanyStore.getState().updateFromWsEvent(event)
          useAgentsStore.getState().updateFromWsEvent(event)
        },
      })),
    [],
  )

  const { connected: wsConnected, setupError: wsSetupError } = useWebSocket({
    bindings,
  })

  // Derive React Flow nodes/edges from store data
  const { nodes, edges } = useMemo(() => {
    if (!config) return { nodes: [], edges: [] }
    const tree = buildOrgTree(config, runtimeStatuses, departmentHealths)
    const layoutNodes = applyDagreLayout(tree.nodes, tree.edges)
    return { nodes: layoutNodes, edges: tree.edges }
  }, [config, runtimeStatuses, departmentHealths])

  return {
    nodes,
    edges,
    loading,
    error,
    wsConnected,
    wsSetupError,
  }
}
