import { useCallback, useEffect, useMemo } from 'react'
import { createLogger } from '@/lib/logger'
import type { Node, Edge } from '@xyflow/react'
import { useCompanyStore } from '@/stores/company'
import { useAgentsStore } from '@/stores/agents'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { usePolling } from '@/hooks/usePolling'
import { useCommunicationEdges } from '@/hooks/useCommunicationEdges'
import { buildOrgTree } from '@/pages/org/build-org-tree'
import { applyDagreLayout } from '@/pages/org/layout'
import { computeForceLayout } from '@/pages/org/force-layout'
import type { CommunicationLink } from '@/pages/org/aggregate-messages'
import type { CommunicationEdgeData } from '@/pages/org/CommunicationEdge'
import type { ViewMode } from '@/pages/org/OrgChartToolbar'
import type { WsChannel } from '@/api/types'

const log = createLogger('useOrgChartData')

const ORG_POLL_INTERVAL = 30_000
const ORG_CHANNELS = ['agents'] as const satisfies readonly WsChannel[]

export interface UseOrgChartDataReturn {
  nodes: Node[]
  edges: Edge[]
  loading: boolean
  error: string | null
  commLoading: boolean
  commError: string | null
  commTruncated: boolean
  wsConnected: boolean
  wsSetupError: string | null
}

function buildCommunicationEdges(
  links: CommunicationLink[],
): Edge[] {
  const maxVolume = Math.max(1, ...links.map((l) => l.volume))
  return links.map((link) => ({
    id: `comm:${encodeURIComponent(link.source)}::${encodeURIComponent(link.target)}`,
    source: link.source,
    target: link.target,
    type: 'communication',
    data: {
      volume: link.volume,
      frequency: link.frequency,
      maxVolume,
    } satisfies CommunicationEdgeData,
  }))
}

export function useOrgChartData(viewMode: ViewMode = 'hierarchy'): UseOrgChartDataReturn {
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
        companyStore.fetchDepartmentHealths().catch((err: unknown) => {
          log.warn('fetchDepartmentHealths failed:', err)
        })
      }
      polling.start()
    }).catch((err: unknown) => {
      log.warn('fetchCompanyData failed:', err)
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

  // Communication data for force view (only fetched when needed)
  const { links: commLinks, loading: commLoading, error: commError, truncated: commTruncated } = useCommunicationEdges(
    viewMode === 'force',
  )

  // Derive React Flow nodes/edges from store data
  const { nodes, edges } = useMemo(() => {
    if (!config) return { nodes: [], edges: [] }

    const tree = buildOrgTree(config, runtimeStatuses, departmentHealths)

    if (viewMode === 'force') {
      // Force view: only agent/ceo nodes (no department groups), communication edges
      const agentNodes = tree.nodes.filter((n) => n.type === 'agent' || n.type === 'ceo')
      // Remove parentId so nodes are not grouped inside departments
      const freeNodes = agentNodes.map((n) => ({ ...n, parentId: undefined }))
      // Filter links to only include edges between visible nodes
      const visibleIds = new Set(freeNodes.map((n) => n.id))
      const filteredLinks = commLinks.filter(
        (l) => visibleIds.has(l.source) && visibleIds.has(l.target),
      )
      const layoutNodes = computeForceLayout(freeNodes, filteredLinks)
      const commEdges = buildCommunicationEdges(filteredLinks)
      return { nodes: layoutNodes, edges: commEdges }
    }

    // Hierarchy view: dagre layout with department groups
    const layoutNodes = applyDagreLayout(tree.nodes, tree.edges)
    return { nodes: layoutNodes, edges: tree.edges }
  }, [config, runtimeStatuses, departmentHealths, viewMode, commLinks])

  return {
    nodes,
    edges,
    loading,
    error,
    commLoading,
    commError,
    commTruncated,
    wsConnected,
    wsSetupError,
  }
}
