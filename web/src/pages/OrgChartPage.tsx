import { useCallback, useMemo, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  useReactFlow,
  type Node,
} from '@xyflow/react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { AlertTriangle, GitBranch } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { useOrgChartData } from '@/hooks/useOrgChartData'
import { useRegisterCommands } from '@/hooks/useCommandPalette'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useToastStore } from '@/stores/toast'
import { AgentNode } from './org/AgentNode'
import { CeoNode } from './org/CeoNode'
import { DepartmentGroupNode } from './org/DepartmentGroupNode'
import { HierarchyEdge } from './org/HierarchyEdge'
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

// Declared outside component for stable reference identity (prevents unnecessary re-renders)
const nodeTypes = { agent: AgentNode, ceo: CeoNode, department: DepartmentGroupNode }
const edgeTypes = { hierarchy: HierarchyEdge }

const VIEWPORT_KEY = 'synthorg:orgchart:viewport'

interface ViewportState {
  x: number
  y: number
  zoom: number
}

function saveViewport(viewport: ViewportState) {
  try {
    localStorage.setItem(VIEWPORT_KEY, JSON.stringify(viewport))
  } catch {
    // localStorage may be full or unavailable
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
  } catch {
    // Invalid stored value
  }
  return undefined
}

interface ContextMenuState {
  nodeId: string
  nodeType: 'agent' | 'ceo' | 'department'
  position: { x: number; y: number }
}

function OrgChartInner() {
  const { nodes, edges, loading, error, wsConnected, wsSetupError } = useOrgChartData()
  const [viewMode, setViewMode] = useState<ViewMode>('hierarchy')
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ nodeId: string; label: string } | null>(null)
  const { fitView, zoomIn, zoomOut } = useReactFlow()
  const addToast = useToastStore((s) => s.add)
  const navigate = useNavigate()

  const defaultViewport = useMemo(() => loadViewport(), [])

  // Register page-local commands
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

  const handleNodeContextMenu = useCallback(
    (event: ReactMouseEvent, node: Node) => {
      event.preventDefault()
      if (!VALID_NODE_TYPES.has(node.type ?? '')) return
      const nodeType = node.type as ContextMenuState['nodeType']
      setContextMenu({
        nodeId: node.id,
        nodeType,
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
      const node = nodes.find((n) => n.id === nodeId)
      if (!node) return
      const name = getAgentName(node)
      if (name) {
        navigate(`/agents/${encodeURIComponent(name)}`)
      }
    },
    [nodes, navigate],
  )

  const handleDelete = useCallback(
    (nodeId: string) => {
      const node = nodes.find((n) => n.id === nodeId)
      const label = node ? getNodeLabel(node).slice(0, 64) : nodeId
      setDeleteConfirm({ nodeId, label })
    },
    [nodes],
  )

  const confirmDelete = useCallback(() => {
    addToast({
      variant: 'info',
      title: 'Delete -- not yet available',
      description: 'Backend API for this operation is pending',
    })
    setDeleteConfirm(null)
  }, [addToast])

  const handleViewModeChange = useCallback(
    (mode: ViewMode) => {
      if (mode === 'force') {
        addToast({
          variant: 'info',
          title: 'Communication view -- not yet available',
          description: 'Force-directed layout requires communication data APIs',
        })
        return
      }
      setViewMode(mode)
    },
    [addToast],
  )

  const handleMoveEnd = useCallback(
    (_event: unknown, viewport: ViewportState) => {
      saveViewport(viewport)
    },
    [],
  )

  const handlePaneClick = useCallback(() => {
    setContextMenu(null)
  }, [])

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
      {/* Error banners */}
      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
          {error}
        </div>
      )}
      {!wsConnected && wsSetupError && (
        <div role="status" aria-live="polite" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
          Real-time updates unavailable: {wsSetupError}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-between pb-3">
        <OrgChartToolbar
          viewMode={viewMode}
          onViewModeChange={handleViewModeChange}
          onFitView={() => fitView({ padding: 0.2 })}
          onZoomIn={() => zoomIn()}
          onZoomOut={() => zoomOut()}
        />
      </div>

      {/* Canvas */}
      <div className="relative flex-1 rounded-lg border border-border">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          defaultViewport={defaultViewport}
          fitView={!defaultViewport}
          fitViewOptions={{ padding: 0.2 }}
          onMoveEnd={handleMoveEnd}
          onNodeClick={handleNodeClick}
          onNodeContextMenu={handleNodeContextMenu}
          onPaneClick={handlePaneClick}
          nodesConnectable={false}
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--color-border)" gap={24} size={1} />
        </ReactFlow>

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

      {/* Delete confirmation dialog */}
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
