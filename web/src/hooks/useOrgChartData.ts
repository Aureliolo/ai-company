import { useCallback, useEffect, useMemo } from 'react'
import { createLogger } from '@/lib/logger'
import type { Node, Edge } from '@xyflow/react'
import { useCompanyStore } from '@/stores/company'
import { useAgentsStore } from '@/stores/agents'
import { useAuthStore } from '@/stores/auth'
import { useOrgChartPrefs } from '@/stores/org-chart-prefs'
import { useWebSocket, type ChannelBinding } from '@/hooks/useWebSocket'
import { usePolling } from '@/hooks/usePolling'
import { useCommunicationEdges } from '@/hooks/useCommunicationEdges'
import { buildOrgTree, type OwnerInfo } from '@/pages/org/build-org-tree'
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
  /** All tree nodes before collapse filtering -- used for search indexing. */
  allNodes: Node[]
  loading: boolean
  error: string | null
  commLoading: boolean
  commError: string | null
  commTruncated: boolean
  wsConnected: boolean
  wsSetupError: string | null
}

export interface UseOrgChartDataOptions {
  viewMode?: ViewMode
  /**
   * Department group IDs that are currently collapsed.  Child agents
   * of collapsed depts are filtered out BEFORE the dagre layout pass
   * so the dept box's computed height shrinks to header-only -- no
   * wasted space below the header where agents would have been.
   */
  collapsedDeptIds?: ReadonlySet<string>
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

export function useOrgChartData(
  viewMode: ViewMode = 'hierarchy',
  collapsedDeptIds?: ReadonlySet<string>,
): UseOrgChartDataReturn {
  const config = useCompanyStore((s) => s.config)
  const departmentHealths = useCompanyStore((s) => s.departmentHealths)
  const loading = useCompanyStore((s) => s.loading)
  const error = useCompanyStore((s) => s.error)
  const runtimeStatuses = useAgentsStore((s) => s.runtimeStatuses)
  const currentUser = useAuthStore((s) => s.user)

  // Visual prefs that affect how much space the dept card chrome
  // takes up.  Passed through to `applyDagreLayout` so the reserved
  // header/footer space matches whatever the user currently has
  // toggled on -- no dead whitespace when budget bar / status dots
  // / add agent are off.
  const showBudgetBar = useOrgChartPrefs((s) => s.showBudgetBar)
  const showStatusDots = useOrgChartPrefs((s) => s.showStatusDots)
  const showAddAgentButton = useOrgChartPrefs((s) => s.showAddAgentButton)

  // Synthesise owner list from the current session user.  Designed
  // as an array so #1082 (multi-user ownership + per-dept admins)
  // can pass multiple owners without changing this shape -- today
  // it is exactly one element.
  const owners = useMemo<OwnerInfo[]>(() => {
    if (!currentUser) return []
    return [{ id: currentUser.id, displayName: currentUser.username }]
  }, [currentUser])

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
  const { nodes, edges, allNodes } = useMemo(() => {
    if (!config) return { nodes: [], edges: [], allNodes: [] }

    const tree = buildOrgTree(config, runtimeStatuses, departmentHealths, owners)

    // Snapshot the full tree BEFORE collapse filtering so consumers
    // (e.g. search) can index every node regardless of which
    // departments are collapsed.
    const allNodes = [...tree.nodes]

    // Filter out child agents of collapsed departments BEFORE layout
    // so the dagre pass computes correct (smaller) dept box sizes.
    // The dept group nodes themselves stay, with an `isCollapsed`
    // flag injected into their data so the UI can render the correct
    // chevron state.  Only applies in hierarchy mode -- the force
    // view strips departments entirely, so collapsing is irrelevant.
    if (viewMode === 'hierarchy' && collapsedDeptIds && collapsedDeptIds.size > 0) {
      tree.nodes = tree.nodes
        .filter((n) => !(n.parentId && collapsedDeptIds.has(n.parentId)))
        .map((n) =>
          n.type === 'department' && collapsedDeptIds.has(n.id)
            ? { ...n, data: { ...n.data, isCollapsed: true } }
            : n,
        )
      const remainingNodeIds = new Set(tree.nodes.map((n) => n.id))
      tree.edges = tree.edges.filter(
        (e) => remainingNodeIds.has(e.source) && remainingNodeIds.has(e.target),
      )
    }

    if (viewMode === 'force') {
      // Force view: only agent/ceo nodes (no department groups, no
      // owner nodes, no hidden layout edges).  Communication view is
      // about agent-to-agent message flow, so the hierarchy scaffold
      // is intentionally stripped.
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
      return { nodes: layoutNodes, edges: commEdges, allNodes }
    }

    // Hierarchy view: dagre layout with department groups
    const layoutNodes = applyDagreLayout(tree.nodes, tree.edges, {
      showBudgetBar,
      showStatusDots,
      showAddAgentButton,
    })
    return { nodes: layoutNodes, edges: tree.edges, allNodes }
  }, [
    config,
    runtimeStatuses,
    departmentHealths,
    viewMode,
    commLinks,
    owners,
    collapsedDeptIds,
    showBudgetBar,
    showStatusDots,
    showAddAgentButton,
  ])

  return {
    nodes,
    edges,
    allNodes,
    loading,
    error,
    commLoading,
    commError,
    commTruncated,
    wsConnected,
    wsSetupError,
  }
}
