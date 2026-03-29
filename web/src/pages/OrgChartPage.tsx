import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  useReactFlow,
  type Node,
  type Edge,
} from '@xyflow/react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { AlertTriangle, GitBranch, Loader2 } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { useOrgChartData } from '@/hooks/useOrgChartData'
import { useRegisterCommands } from '@/hooks/useCommandPalette'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useToastStore } from '@/stores/toast'
import { useCompanyStore } from '@/stores/company'
import { prefersReducedMotion } from '@/lib/motion'
import { findDropTarget, type DepartmentBounds } from './org/drop-target'
import { AgentNode } from './org/AgentNode'
import { CeoNode } from './org/CeoNode'
import { DepartmentGroupNode } from './org/DepartmentGroupNode'
import { HierarchyEdge } from './org/HierarchyEdge'
import { CommunicationEdge } from './org/CommunicationEdge'
import { OrgChartToolbar, type ViewMode } from './org/OrgChartToolbar'
import { OrgChartSkeleton } from './org/OrgChartSkeleton'
import { NodeContextMenu } from './org/NodeContextMenu'
import type { AgentNodeData, DepartmentGroupData } from './org/build-org-tree'
import { ROUTES } from '@/router/routes'

const VALID_NODE_TYPES = new Set(['agent', 'ceo', 'department'])

function getNodeLabel(node: Node): string {
  switch (node.type) {
    case 'agent':
    case 'ceo':
      return (node.data as AgentNodeData).name
    case 'department':
      return (node.data as DepartmentGroupData).displayName
    default:
      return node.id
  }
}

function getAgentName(node: Node): string | undefined {
  if (node.type === 'agent' || node.type === 'ceo') {
    const name = (node.data as AgentNodeData).name
    return typeof name === 'string' ? name : undefined
  }
  return undefined
}

// Approximate agent node dimensions for center-point hit testing during drag
const AGENT_NODE_WIDTH = 160
const AGENT_NODE_HEIGHT = 80

// Declared outside component for stable reference identity
const nodeTypes = { agent: AgentNode, ceo: CeoNode, department: DepartmentGroupNode }
const edgeTypes = { hierarchy: HierarchyEdge, communication: CommunicationEdge }

const VIEWPORT_KEY = 'synthorg:orgchart:viewport'

interface ViewportState {
  x: number
  y: number
  zoom: number
}

function saveViewport(viewport: ViewportState) {
  try {
    localStorage.setItem(VIEWPORT_KEY, JSON.stringify(viewport))
  } catch (err) {
    console.warn('[OrgChart] Failed to save viewport:', err)
  }
}

function loadViewport(): ViewportState | undefined {
  try {
    const stored = localStorage.getItem(VIEWPORT_KEY)
    if (!stored) return undefined
    const parsed: unknown = JSON.parse(stored)
    if (
      typeof parsed === 'object' && parsed !== null &&
      typeof (parsed as Record<string, unknown>).x === 'number' &&
      typeof (parsed as Record<string, unknown>).y === 'number' &&
      typeof (parsed as Record<string, unknown>).zoom === 'number'
    ) {
      return parsed as ViewportState
    }
  } catch (err) {
    console.warn('[OrgChart] Failed to load viewport:', err)
  }
  return undefined
}

// ── View transition animation ─────────────────────────────────

const TRANSITION_DURATION_MS = 400

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
  const { nodes, edges, loading, error, commLoading, commError, commTruncated, wsConnected, wsSetupError } =
    useOrgChartData(viewMode)

  const [transition, dispatch] = useReducer(transitionReducer, {
    displayNodes: [],
    displayEdges: [],
    transitioning: false,
  })

  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ nodeId: string; label: string } | null>(null)
  const [dragOverDeptId, setDragOverDeptId] = useState<string | null>(null)
  const dragOverDeptIdRef = useRef<string | null>(null)
  const { fitView, zoomIn, zoomOut } = useReactFlow()
  const addToast = useToastStore((s) => s.add)
  const navigate = useNavigate()
  const prevNodesRef = useRef<Node[]>([])
  const animFrameRef = useRef<number | null>(null)
  const announceRef = useRef<HTMLDivElement>(null)
  const dragOriginalDeptRef = useRef<string | null>(null)

  const defaultViewport = useMemo(() => loadViewport(), [])

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

  useRegisterCommands([
    {
      id: 'org-fit-view',
      label: 'Fit to View',
      description: 'Reset zoom to fit all nodes',
      icon: GitBranch,
      action: () => fitView({ padding: 0.2 }),
      group: 'Org Chart',
      scope: 'local',
    },
  ])

  // Animate transitions between view modes using reducer (avoids set-state-in-effect)
  useEffect(() => {
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
      const name = getAgentName(node)
      if (name) {
        navigate(`/agents/${encodeURIComponent(name)}`)
      }
    },
    [navigate],
  )

  const handleViewDetails = useCallback(
    (nodeId: string) => {
      const node = transition.displayNodes.find((n) => n.id === nodeId)
      if (!node) return
      const name = getAgentName(node)
      if (name) {
        navigate(`/agents/${encodeURIComponent(name)}`)
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

  // Apply isDropTarget highlighting to department nodes during drag
  const renderedNodes = useMemo(() => {
    if (!dragOverDeptId) return transition.displayNodes
    return transition.displayNodes.map((n) =>
      n.type === 'department'
        ? { ...n, data: { ...n.data, isDropTarget: n.id === dragOverDeptId } }
        : n,
    )
  }, [transition.displayNodes, dragOverDeptId])

  if (loading && transition.displayNodes.length === 0) {
    return <OrgChartSkeleton />
  }

  if (!loading && transition.displayNodes.length === 0 && !error) {
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
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
          {error}
        </div>
      )}
      {commError && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
          Communication data unavailable: {commError}
        </div>
      )}
      {commTruncated && !commError && (
        <div role="status" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
          Communication graph shows partial data (message limit reached)
        </div>
      )}
      {!wsConnected && wsSetupError && (
        <div role="status" aria-live="polite" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
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
        {/* Drag-drop visual feedback styles */}
        <style>{`
          .react-flow__node.dragging {
            opacity: var(--so-opacity-dragging, 0.6);
            transform: scale(1.02);
            z-index: 1000 !important;
          }
          .react-flow__node.dragging > div {
            box-shadow: var(--so-shadow-card-hover);
          }
          .react-flow__node {
            transition: transform 0.4s cubic-bezier(0.17, 0.67, 0.29, 1.01);
          }
          @media (prefers-reduced-motion: reduce) {
            .react-flow__node { transition: none; }
          }
        `}</style>
        <ReactFlow
          nodes={renderedNodes}
          edges={transition.displayEdges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          defaultViewport={defaultViewport}
          fitView={!defaultViewport}
          fitViewOptions={{ padding: 0.2 }}
          onMoveEnd={handleMoveEnd}
          onNodeClick={handleNodeClick}
          onNodeContextMenu={handleNodeContextMenu}
          onNodeDragStart={viewMode === 'hierarchy' ? handleNodeDragStart : undefined}
          onNodeDrag={viewMode === 'hierarchy' ? handleNodeDrag : undefined}
          onNodeDragStop={viewMode === 'hierarchy' ? handleNodeDragStop : undefined}
          onPaneClick={handlePaneClick}
          nodesConnectable={false}
          nodesDraggable={viewMode === 'hierarchy'}
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--color-border)" gap={24} size={1} />
        </ReactFlow>

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
    <div className="flex h-full flex-col gap-4">
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
