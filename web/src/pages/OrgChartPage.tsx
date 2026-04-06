import { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  MiniMap,
  useReactFlow,
  type Node,
  type Edge,
} from '@xyflow/react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { AlertTriangle, GitBranch, Loader2 } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { createLogger } from '@/lib/logger'
import { useOrgChartData } from '@/hooks/useOrgChartData'
import { useRegisterCommands } from '@/hooks/useCommandPalette'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useToastStore } from '@/stores/toast'
import { useCompanyStore } from '@/stores/company'
import { useOrgChartPrefs } from '@/stores/org-chart-prefs'
import { useLiveEdgeActivity } from '@/hooks/useLiveEdgeActivity'
import { prefersReducedMotion, TRANSITION_SLOW_MS } from '@/lib/motion'
import { findDropTarget, type DepartmentBounds } from './org/drop-target'
import { AgentNode } from './org/AgentNode'
import { CeoNode } from './org/CeoNode'
import { DepartmentGroupNode } from './org/DepartmentGroupNode'
import { TeamGroupNode } from './org/TeamGroupNode'
import { OwnerNode } from './org/OwnerNode'
import { HierarchyEdge } from './org/HierarchyEdge'
import { CommunicationEdge } from './org/CommunicationEdge'
import { OrgChartToolbar, type ViewMode } from './org/OrgChartToolbar'
import { OrgChartSkeleton } from './org/OrgChartSkeleton'
import { OrgChartSearchOverlay } from './org/OrgChartSearchOverlay'
import { NodeContextMenu } from './org/NodeContextMenu'
import type { AgentNodeData, DepartmentGroupData, OwnerNodeData } from './org/build-org-tree'
import { ROUTES } from '@/router/routes'

const log = createLogger('OrgChart')

const VALID_NODE_TYPES = new Set(['agent', 'ceo', 'department'])

function getNodeLabel(node: Node): string {
  switch (node.type) {
    case 'agent':
    case 'ceo':
      return (node.data as AgentNodeData).name
    case 'department':
      return (node.data as DepartmentGroupData).displayName
    case 'owner':
      return (node.data as OwnerNodeData).displayName
    default:
      return node.id
  }
}

// Approximate agent node dimensions for center-point hit testing during drag
const AGENT_NODE_WIDTH = 160
const AGENT_NODE_HEIGHT = 80

// Declared outside component for stable reference identity
const nodeTypes = {
  agent: AgentNode,
  ceo: CeoNode,
  department: DepartmentGroupNode,
  team: TeamGroupNode,
  owner: OwnerNode,
}
const edgeTypes = { hierarchy: HierarchyEdge, communication: CommunicationEdge }

const VIEWPORT_KEY = 'synthorg:orgchart:viewport'
const COLLAPSED_DEPTS_KEY = 'synthorg:orgchart:collapsed-depts'

// NOTE: the MiniMap no longer renders text labels inside the dept
// rectangles.  At the scale the minimap displays (~240x180 px for
// the full org) the available font size is ~2-3 px tall which is
// unreadable regardless of font weight -- the labels ended up
// as visual clutter the user couldn't actually use.  Shapes +
// colors alone convey position well enough, and a default-off
// toggle lets users opt in or out entirely.

interface ViewportState {
  x: number
  y: number
  zoom: number
}

function saveViewport(viewport: ViewportState) {
  try {
    localStorage.setItem(VIEWPORT_KEY, JSON.stringify(viewport))
  } catch (err) {
    log.warn('Failed to save viewport:', err)
  }
}

// NOTE: loadViewport() was removed -- the chart used to load a persisted
// viewport from localStorage on mount, which could point at empty space
// if the org had been restructured between sessions and leave the chart
// looking blank on first load.  We now rely on ReactFlow's `fitView`
// prop to centre the camera on whatever nodes are actually present;
// saveViewport() is still called from onMoveEnd so pan/zoom state
// survives in-session refreshes if a user clears + rezooms.

// ── View transition animation ─────────────────────────────────

const TRANSITION_DURATION_MS = TRANSITION_SLOW_MS

function tweenSlowEase(t: number): number {
  if (t <= 0) return 0
  if (t >= 1) return 1
  return t < 0.5
    ? 4 * t * t * t
    : 1 - (-2 * t + 2) ** 3 / 2
}

function interpolateNodes(from: Node[], to: Node[], progress: number): Node[] {
  const toMap = new Map(to.map((n) => [n.id, n]))
  const fromMap = new Map(from.map((n) => [n.id, n]))
  const result: Node[] = []

  for (const target of to) {
    const source = fromMap.get(target.id)
    if (source) {
      result.push({
        ...target,
        position: {
          x: source.position.x + (target.position.x - source.position.x) * progress,
          y: source.position.y + (target.position.y - source.position.y) * progress,
        },
      })
    } else {
      result.push(target)
    }
  }

  if (progress < 1) {
    for (const source of from) {
      if (!toMap.has(source.id)) {
        result.push(source)
      }
    }
  }

  return result
}

// ── Transition reducer ────────────────────────────────────────

interface TransitionState {
  displayNodes: Node[]
  displayEdges: Edge[]
  transitioning: boolean
}

type TransitionAction =
  | { type: 'snap'; nodes: Node[]; edges: Edge[] }
  | { type: 'start'; edges: Edge[] }
  | { type: 'frame'; nodes: Node[] }
  | { type: 'end'; nodes: Node[] }

function transitionReducer(state: TransitionState, action: TransitionAction): TransitionState {
  switch (action.type) {
    case 'snap':
      return { displayNodes: action.nodes, displayEdges: action.edges, transitioning: false }
    case 'start':
      return { ...state, displayEdges: action.edges, transitioning: true }
    case 'frame':
      return { ...state, displayNodes: action.nodes }
    case 'end':
      return { ...state, displayNodes: action.nodes, transitioning: false }
  }
}

// ── Context menu state ────────────────────────────────────────

interface ContextMenuState {
  nodeId: string
  nodeType: 'agent' | 'ceo' | 'department'
  position: { x: number; y: number }
}

function OrgChartInner() {
  const [viewMode, setViewMode] = useState<ViewMode>('hierarchy')

  const [transition, dispatch] = useReducer(transitionReducer, {
    displayNodes: [],
    displayEdges: [],
    transitioning: false,
  })

  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ nodeId: string; label: string } | null>(null)
  const [dragOverDeptId, setDragOverDeptId] = useState<string | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [collapsedDepts, setCollapsedDepts] = useState<Set<string>>(() => {
    // Persist user's collapse/expand preferences across sessions so
    // they do not have to re-toggle every visit.
    try {
      const stored = localStorage.getItem(COLLAPSED_DEPTS_KEY)
      if (stored) return new Set<string>(JSON.parse(stored))
    } catch (err) {
      log.warn('Failed to load collapsed depts from localStorage:', err)
    }
    return new Set()
  })
  const dragOverDeptIdRef = useRef<string | null>(null)

  const toggleDeptCollapsed = useCallback((deptId: string) => {
    setCollapsedDepts((prev) => {
      const next = new Set(prev)
      if (next.has(deptId)) next.delete(deptId)
      else next.add(deptId)
      try {
        localStorage.setItem(COLLAPSED_DEPTS_KEY, JSON.stringify([...next]))
      } catch (err) {
        log.warn('Failed to persist collapsed depts:', err)
      }
      return next
    })
  }, [])

  const { nodes, edges, allNodes, loading, error, commLoading, commError, commTruncated, wsConnected, wsSetupError } =
    useOrgChartData(viewMode, collapsedDepts)

  const particleFlowMode = useOrgChartPrefs((s) => s.particleFlowMode)
  const showMinimap = useOrgChartPrefs((s) => s.showMinimap)

  // Map of `sender::target` agent pair → edge ID, used by the live
  // activity hook to look up which edge to flash when a new message
  // arrives.  Only populated in `live` mode to avoid the subscription
  // cost in the other two modes.
  const edgeIdByAgentPair = useMemo(() => {
    const map = new Map<string, string>()
    if (particleFlowMode !== 'live') return map
    for (const edge of edges) {
      if (edge.hidden) continue
      map.set(`${edge.source}::${edge.target}`, edge.id)
    }
    return map
  }, [edges, particleFlowMode])

  const liveActiveEdgeIds = useLiveEdgeActivity(edgeIdByAgentPair)

  const { fitView, zoomIn, zoomOut } = useReactFlow()
  const addToast = useToastStore((s) => s.add)
  const navigate = useNavigate()
  const prevNodesRef = useRef<Node[]>([])
  const animFrameRef = useRef<number | null>(null)
  const announceRef = useRef<HTMLDivElement>(null)
  const dragOriginalDeptRef = useRef<string | null>(null)

  // NOTE: loadViewport() is intentionally NOT called here.  We used to
  // pass the persisted viewport as `defaultViewport` to ReactFlow, but
  // stale persisted viewports from a previous session can point at
  // empty space and make the chart look blank on first load.  The
  // `onMoveEnd` handler still persists the live viewport so pan/zoom
  // state survives in-session refreshes; `fitView` on mount centers
  // whatever nodes are actually present.

  const announce = useCallback((msg: string) => {
    if (announceRef.current) announceRef.current.textContent = msg
  }, [])

  // Compute department bounds for drop target detection
  const deptBounds = useMemo<DepartmentBounds[]>(() => {
    return transition.displayNodes
      .filter((n) => n.type === 'department')
      .map((n) => ({
        departmentName: (n.data as import('./org/build-org-tree').DepartmentGroupData).departmentName,
        nodeId: n.id,
        x: n.position.x,
        y: n.position.y,
        width: (n.measured?.width ?? n.width ?? 200) as number,
        height: (n.measured?.height ?? n.height ?? 120) as number,
      }))
  }, [transition.displayNodes])

  // Memoized so the registration effect inside useRegisterCommands does not
  // tear down and re-create the command on every render (which would thrash
  // the command palette's subscriber set and trigger cascading re-renders).
  const orgChartCommands = useMemo(
    () => [
      {
        id: 'org-fit-view',
        label: 'Fit to View',
        description: 'Reset zoom to fit all nodes',
        icon: GitBranch,
        action: () => fitView({ padding: 0.2 }),
        group: 'Org Chart',
        scope: 'local' as const,
      },
    ],
    [fitView],
  )
  useRegisterCommands(orgChartCommands)

  // Animate transitions between view modes using a reducer.  This is
  // deliberately a `useLayoutEffect`, not `useEffect`, so the snap
  // dispatch on initial load runs synchronously after the render that
  // resolved `nodes` (via `useOrgChartData`'s memo) and BEFORE the
  // browser paints.  With `useEffect`, there was a visible flash
  // between the "data loaded, but `transition.displayNodes` is still
  // empty" render and the subsequent dispatch+rerender -- the chart
  // briefly showed the empty-state UI or an empty canvas.  Layout
  // effects block the commit phase, so the user only sees the
  // post-snap state on the first paint.
  useLayoutEffect(() => {
    // Cancel any in-flight animation
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }

    // Use on-screen positions as the animation starting point so mid-animation
    // restarts interpolate from the actual displayed positions, not the canceled target.
    const fromNodes = transition.displayNodes.length > 0 ? transition.displayNodes : prevNodesRef.current

    // Snap instantly: empty, reduced motion, or first render
    if (nodes.length === 0 || prefersReducedMotion() || fromNodes.length === 0) {
      prevNodesRef.current = nodes
      dispatch({ type: 'snap', nodes, edges })
      return
    }

    // Animate position interpolation
    prevNodesRef.current = nodes
    dispatch({ type: 'start', edges })

    const startTime = performance.now()

    function animate(now: number) {
      const elapsed = now - startTime
      const rawProgress = Math.min(elapsed / TRANSITION_DURATION_MS, 1)
      const easedProgress = tweenSlowEase(rawProgress)

      if (rawProgress < 1) {
        dispatch({ type: 'frame', nodes: interpolateNodes(fromNodes, nodes, easedProgress) })
        animFrameRef.current = requestAnimationFrame(animate)
      } else {
        dispatch({ type: 'end', nodes })
        animFrameRef.current = null
      }
    }

    animFrameRef.current = requestAnimationFrame(animate)

    return () => {
      if (animFrameRef.current !== null) {
        cancelAnimationFrame(animFrameRef.current)
        animFrameRef.current = null
      }
    }
  // eslint-disable-next-line @eslint-react/exhaustive-deps -- transition.displayNodes is read for starting position only; including it would cause infinite loops
  }, [nodes, edges])

  const handleNodeContextMenu = useCallback(
    (event: ReactMouseEvent, node: Node) => {
      event.preventDefault()
      if (!VALID_NODE_TYPES.has(node.type ?? '')) return
      setContextMenu({
        nodeId: node.id,
        nodeType: node.type as ContextMenuState['nodeType'],
        position: { x: event.clientX, y: event.clientY },
      })
    },
    [],
  )

  const handleNodeClick = useCallback(
    (_event: ReactMouseEvent, node: Node) => {
      // Navigate by agent id (which is `node.id` in React Flow) --
      // ids are URL-safe by construction, names are not.
      if (node.type === 'agent' || node.type === 'ceo') {
        navigate(`/agents/${encodeURIComponent(node.id)}`)
      }
    },
    [navigate],
  )

  const handleViewDetails = useCallback(
    (nodeId: string) => {
      const node = transition.displayNodes.find((n) => n.id === nodeId)
      if (!node) return
      if (node.type === 'agent' || node.type === 'ceo') {
        navigate(`/agents/${encodeURIComponent(node.id)}`)
      }
    },
    [transition.displayNodes, navigate],
  )

  const handleDelete = useCallback(
    (nodeId: string) => {
      const node = transition.displayNodes.find((n) => n.id === nodeId)
      const label = node ? getNodeLabel(node).slice(0, 64) : nodeId
      setDeleteConfirm({ nodeId, label })
    },
    [transition.displayNodes],
  )

  const confirmDelete = useCallback(() => {
    addToast({
      variant: 'info',
      title: 'Delete -- not yet available',
      description: 'Backend API for this operation is pending',
    })
    setDeleteConfirm(null)
  }, [addToast])

  const handleViewModeChange = useCallback((mode: ViewMode) => {
    setViewMode(mode)
  }, [])

  const handleMoveEnd = useCallback((_event: unknown, viewport: ViewportState) => {
    saveViewport(viewport)
  }, [])

  const handlePaneClick = useCallback(() => {
    setContextMenu(null)
  }, [])

  // Ctrl+F / Cmd+F opens the search overlay.  Escape closes it.
  // We preventDefault() so the browser's native find-in-page doesn't
  // fire on top of our overlay.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
        e.preventDefault()
        setSearchOpen(true)
      } else if (e.key === 'Escape' && searchOpen) {
        e.preventDefault()
        setSearchOpen(false)
        setSearchQuery('')
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [searchOpen])

  const handleSearchClose = useCallback(() => {
    setSearchOpen(false)
    setSearchQuery('')
  }, [])

  // ── Drag-drop handlers (hierarchy view only) ────────────────

  const handleNodeDragStart = useCallback(
    (_event: ReactMouseEvent, node: Node) => {
      if (node.type !== 'agent') return
      if (viewMode !== 'hierarchy') return
      const dept = (node.data as AgentNodeData).department
      dragOriginalDeptRef.current = dept
      const name = (node.data as AgentNodeData).name
      announce(`Started dragging ${name}`)
    },
    [viewMode, announce],
  )

  const handleNodeDrag = useCallback(
    (_event: ReactMouseEvent, node: Node) => {
      if (!dragOriginalDeptRef.current) return
      const centerX = node.position.x + ((node.measured?.width ?? AGENT_NODE_WIDTH) / 2)
      const centerY = node.position.y + ((node.measured?.height ?? AGENT_NODE_HEIGHT) / 2)
      const target = findDropTarget({ x: centerX, y: centerY }, deptBounds)
      const newOverId = target?.nodeId ?? null
      const shouldAnnounce = dragOverDeptIdRef.current !== newOverId && target
      dragOverDeptIdRef.current = newOverId
      setDragOverDeptId(newOverId)
      if (shouldAnnounce) {
        queueMicrotask(() => announce(`Over ${target.departmentName}`))
      }
    },
    [deptBounds, announce],
  )

  const handleNodeDragStop = useCallback(
    (_event: ReactMouseEvent, node: Node) => {
      const originalDept = dragOriginalDeptRef.current
      dragOriginalDeptRef.current = null
      dragOverDeptIdRef.current = null
      setDragOverDeptId(null)

      if (!originalDept) return
      if (node.type !== 'agent') return

      const centerX = node.position.x + ((node.measured?.width ?? AGENT_NODE_WIDTH) / 2)
      const centerY = node.position.y + ((node.measured?.height ?? AGENT_NODE_HEIGHT) / 2)
      const target = findDropTarget({ x: centerX, y: centerY }, deptBounds)

      const agentName = (node.data as AgentNodeData).name
      const newDept = target?.departmentName

      if (!newDept || newDept === originalDept) {
        announce(`Cancelled moving ${agentName}`)
        return
      }

      // Optimistic update with rollback
      const rollback = useCompanyStore.getState().optimisticReassignAgent(agentName, newDept)

      useCompanyStore.getState().updateAgent(agentName, { department: newDept })
        .then(() => {
          announce(`Moved ${agentName} to ${newDept}`)
          addToast({ variant: 'success', title: `Moved ${agentName} to ${newDept}` })
        })
        .catch((err: unknown) => {
          rollback()
          const msg = err instanceof Error ? err.message : 'Unknown error'
          const currentDept = useCompanyStore.getState().config?.agents.find((a) => a.name === agentName)?.department
          if (currentDept === originalDept) {
            announce(`Failed to move ${agentName}, returned to ${originalDept}`)
            addToast({ variant: 'error', title: 'Reassignment failed', description: msg })
          } else {
            announce(`Failed to move ${agentName}`)
            addToast({ variant: 'error', title: 'Reassignment failed', description: msg })
          }
        })
    },
    [deptBounds, addToast, announce],
  )

  // Apply isDropTarget highlighting to department nodes during drag.
  //
  // Fallback to the directly-computed `nodes` memo when the reducer
  // hasn't caught up yet.  The snap dispatch runs in a useLayoutEffect
  // so it is nearly always in sync, but using `nodes` as the fallback
  // makes the first render defensive against any race where
  // `transition.displayNodes` is still `[]` while the memo has already
  // produced a populated array -- the chart would otherwise appear
  // empty for one frame even with fresh data in hand.
  const sourceNodes = transition.displayNodes.length > 0 ? transition.displayNodes : nodes

  // Search query normalisation: trimmed and lowercased once here so
  // the predicate in the match set loop is a cheap string includes.
  const normalisedQuery = searchOpen ? searchQuery.trim().toLowerCase() : ''

  // Nodes matching the active search query.  Only populated while
  // the search overlay is open AND the query is non-empty -- an
  // empty query matches nothing (rather than everything) so the
  // user sees zero matches until they start typing.
  //
  // The search indexes `allNodes` (the full pre-collapse tree) so
  // agents inside collapsed departments are still discoverable.
  // Matched nodes that are not currently visible in `sourceNodes`
  // still contribute to the match count so the operator knows
  // results exist even if the department is collapsed.
  const searchMatchIds = useMemo<Set<string> | null>(() => {
    if (!normalisedQuery) return null
    const matches = new Set<string>()
    for (const n of allNodes) {
      const label = getNodeLabel(n).toLowerCase()
      if (label.includes(normalisedQuery)) {
        matches.add(n.id)
        continue
      }
      // Agents also match on role text.
      if (n.type === 'agent' || n.type === 'ceo') {
        const role = (n.data as AgentNodeData).role?.toLowerCase() ?? ''
        if (role.includes(normalisedQuery)) {
          matches.add(n.id)
        }
      }
    }
    return matches
  }, [normalisedQuery, allNodes])

  // Dim-other-nodes highlighting fires ONLY when the search
  // overlay is open and has matches.  Earlier iterations also
  // dimmed on hover-chain, but users reported that as "everything
  // else goes dark which is weird and flickery" -- every mouse
  // move between cards retriggered opacity transitions.  Search
  // is an explicit deliberate action so the dim makes sense there;
  // hover is not and should stay stable.
  // O(1) lookup for all (pre-collapse) nodes -- used by the
  // highlight memo to resolve parent departments for matched
  // agents that may still be in collapsed groups.
  const allNodeById = useMemo(() => {
    const map = new Map<string, (typeof allNodes)[number]>()
    for (const n of allNodes) map.set(n.id, n)
    return map
  }, [allNodes])

  const highlightedNodeIds = useMemo<Set<string> | null>(() => {
    if (!searchMatchIds) return null
    const expanded = new Set<string>(searchMatchIds)
    for (const id of searchMatchIds) {
      const node = allNodeById.get(id)
      if (node?.parentId) expanded.add(node.parentId)
    }
    return expanded
  }, [allNodeById, searchMatchIds])

  const renderedNodes = useMemo(() => {
    return sourceNodes.map((n) => {
      const isDropTarget = dragOverDeptId !== null && n.type === 'department' && n.id === dragOverDeptId
      const isDeptNode = n.type === 'department'
      // Dim non-matches only when the search overlay is open and
      // has matches.  No dimming on hover -- that produced
      // flicker as the mouse moved between cards.
      const dimmed = highlightedNodeIds !== null && !highlightedNodeIds.has(n.id)
      const next = { ...n }

      if (isDeptNode) {
        next.data = { ...n.data, onToggleCollapsed: toggleDeptCollapsed }
      }
      if (isDropTarget) {
        next.data = { ...next.data, isDropTarget: true }
      }
      if (dimmed) {
        next.style = { ...n.style, opacity: 0.25, transition: `opacity var(--so-transition-dim) ease` }
      } else if (n.style && typeof (n.style as { opacity?: number }).opacity === 'number') {
        const rest = { ...n.style } as Record<string, unknown>
        delete rest['opacity']
        next.style = rest
      }
      return next
    })
  }, [sourceNodes, dragOverDeptId, highlightedNodeIds, toggleDeptCollapsed])

  const renderedEdges = useMemo(() => {
    return transition.displayEdges.map((e) => {
      // Resolve whether particles animate on this edge, based on
      // the user's particle flow mode.  In live mode the edge has
      // to have had recent activity; in always mode every edge has
      // particles; in off mode none do.
      const particlesVisible =
        particleFlowMode === 'always'
          ? true
          : particleFlowMode === 'live'
            ? liveActiveEdgeIds.has(e.id)
            : false
      return {
        ...e,
        data: { ...(e.data as object), particlesVisible },
      }
    })
  }, [transition.displayEdges, particleFlowMode, liveActiveEdgeIds])

  // Diagnostic: log once per meaningful shape change so an empty chart
  // in the wild can be traced to which layer is producing zero nodes.
  // Logged at debug level so production builds strip it.
  useLayoutEffect(() => {
    log.debug('OrgChart render sizes', {
      memoNodes: nodes.length,
      memoEdges: edges.length,
      reducerDisplayNodes: transition.displayNodes.length,
      rendered: renderedNodes.length,
      loading,
      hasError: !!error,
    })
  }, [nodes.length, edges.length, transition.displayNodes.length, renderedNodes.length, loading, error])

  // Use the memo's `nodes` for gating, not `transition.displayNodes`.
  // The memo updates synchronously in the same render cycle that
  // receives fresh data from the company store, whereas the reducer is
  // updated via a layout-effect dispatch one render later.  Gating the
  // skeleton / empty-state on the memo makes sure we never hide a
  // populated chart for a frame while the reducer catches up.
  if (loading && nodes.length === 0) {
    return <OrgChartSkeleton />
  }

  if (!loading && nodes.length === 0 && !error) {
    return (
      <EmptyState
        icon={GitBranch}
        title="No organization configured"
        description="Set up your company and agents to see the org chart"
        action={{
          label: 'Edit Organization',
          onClick: () => navigate(ROUTES.ORG_EDIT),
        }}
      />
    )
  }

  return (
    <div className="flex h-full flex-col">
      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
          {error}
        </div>
      )}
      {commError && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-card text-xs text-warning">
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
          Communication data unavailable: {commError}
        </div>
      )}
      {commTruncated && !commError && (
        <div role="status" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-card text-xs text-warning">
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
          Communication graph shows partial data (message limit reached)
        </div>
      )}
      {!wsConnected && wsSetupError && (
        <div role="status" aria-live="polite" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-card text-xs text-warning">
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
          Real-time updates unavailable: {wsSetupError}
        </div>
      )}

      <div className="flex items-center justify-between pb-3">
        <OrgChartToolbar
          viewMode={viewMode}
          onViewModeChange={handleViewModeChange}
          onFitView={() => fitView({ padding: 0.2 })}
          onZoomIn={() => zoomIn()}
          onZoomOut={() => zoomOut()}
        />
        {(commLoading || transition.transitioning) && viewMode === 'force' && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            {commLoading ? 'Loading communication data...' : 'Transitioning...'}
          </div>
        )}
      </div>

      <div className="relative flex-1 rounded-lg border border-border">
        <ReactFlow
          aria-label="Organization chart"
          nodes={renderedNodes}
          edges={renderedEdges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          // Always `fitView` on mount so the camera centers on whatever
          // nodes are currently present.  A stale `defaultViewport`
          // persisted to localStorage from a previous session can
          // otherwise point at empty space -- if the org was restructured,
          // or if the user panned off-canvas before their previous
          // reload, the new nodes land outside the saved window and the
          // chart looks empty even though the nodes exist.  fitView
          // re-applies on every mount; the saved viewport is still
          // honoured for in-session pan/zoom persistence via the
          // onMoveEnd handler below.
          fitView
          fitViewOptions={{ padding: 0.2 }}
          onMoveEnd={handleMoveEnd}
          onNodeClick={handleNodeClick}
          onNodeContextMenu={handleNodeContextMenu}
          // Drag-drop agent reassignment is disabled until the backend
          // CRUD endpoints land -- see #1081.  `updateAgentOrg` (the
          // PATCH /agents/{name} call wired into handleNodeDragStop)
          // does not exist on the backend yet, so dropping an agent
          // onto another department would roll back with a 405.  We
          // set `nodesDraggable={false}` to block dragging entirely;
          // the drag handlers stay wired so the code path is still
          // exercised by tests and easy to re-enable once #1081 lands
          // -- just flip `nodesDraggable` back to `viewMode === 'hierarchy'`.
          onNodeDragStart={viewMode === 'hierarchy' ? handleNodeDragStart : undefined}
          onNodeDrag={viewMode === 'hierarchy' ? handleNodeDrag : undefined}
          onNodeDragStop={viewMode === 'hierarchy' ? handleNodeDragStop : undefined}
          onPaneClick={handlePaneClick}
          nodesConnectable={false}
          nodesDraggable={false}
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--color-border)" gap={24} size={1} />
          {showMinimap && (
            <MiniMap
              pannable
              zoomable
              ariaLabel="Org chart minimap"
              position="bottom-right"
              bgColor="var(--so-minimap-bg)"
              maskColor="var(--so-minimap-mask)"
              maskStrokeColor="var(--so-minimap-stroke)"
              maskStrokeWidth={1.5}
              style={{
                width: 260,
                height: 200,
                resize: 'both',
                overflow: 'hidden',
                border: '1px solid var(--so-minimap-border)',
                borderRadius: '10px',
                boxShadow: 'var(--so-minimap-shadow)',
              }}
              nodeColor={(n) => {
                if (n.type === 'owner') return 'var(--so-minimap-node-owner)'
                if (n.type === 'department') return 'var(--so-minimap-node-dept)'
                return 'var(--so-minimap-node-agent)'
              }}
              nodeStrokeColor={(n) => (n.type === 'department' ? 'var(--so-minimap-stroke)' : 'transparent')}
              nodeStrokeWidth={1.5}
              nodeBorderRadius={4}
            />
          )}
        </ReactFlow>

        <OrgChartSearchOverlay
          open={searchOpen}
          query={searchQuery}
          onQueryChange={setSearchQuery}
          onClose={handleSearchClose}
          matchCount={searchMatchIds?.size ?? 0}
        />

        {/* ARIA live region for drag-drop announcements */}
        <div ref={announceRef} className="sr-only" aria-live="assertive" />

        {contextMenu && (
          <NodeContextMenu
            nodeId={contextMenu.nodeId}
            nodeType={contextMenu.nodeType}
            position={contextMenu.position}
            onClose={() => setContextMenu(null)}
            onViewDetails={handleViewDetails}
            onDelete={handleDelete}
          />
        )}
      </div>

      <ConfirmDialog
        open={deleteConfirm !== null}
        onOpenChange={(open) => { if (!open) setDeleteConfirm(null) }}
        title={`Delete "${deleteConfirm?.label}"?`}
        description="This action cannot be undone."
        variant="destructive"
        confirmLabel="Delete"
        onConfirm={confirmDelete}
      />
    </div>
  )
}

export default function OrgChartPage() {
  return (
    <div className="flex h-full flex-col gap-section-gap">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Org Chart</h1>
        <Button asChild variant="outline" size="sm">
          <Link to={ROUTES.ORG_EDIT}>Edit Organization</Link>
        </Button>
      </div>

      <ErrorBoundary level="section">
        <ReactFlowProvider>
          <OrgChartInner />
        </ReactFlowProvider>
      </ErrorBoundary>
    </div>
  )
}
