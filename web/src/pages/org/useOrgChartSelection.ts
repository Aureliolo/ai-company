import { useCallback, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import type { Node } from '@xyflow/react'
import { useNavigate } from 'react-router'
import { useToastStore } from '@/stores/toast'
import type { AgentNodeData, DepartmentGroupData, OwnerNodeData } from './build-org-tree'

type NodeType = ContextMenuState['nodeType']

const VALID_NODE_TYPES: ReadonlySet<NodeType> = new Set<NodeType>([
  'agent',
  'ceo',
  'department',
])

function isValidNodeType(value: string | undefined): value is NodeType {
  return value !== undefined && (VALID_NODE_TYPES as ReadonlySet<string>).has(value)
}

/** Non-null, non-array, object-shaped value (shared pre-check for shape guards). */
function isObjectRecord(data: unknown): data is Record<string, unknown> {
  return typeof data === 'object' && data !== null && !Array.isArray(data)
}

/**
 * Build a type predicate that asserts every listed field is a non-empty
 * ``string`` on the input object. Used by the node-data shape guards so
 * each one validates the full string-typed surface of its interface,
 * not just one field.
 */
function makeStringFieldGuard<T>(
  requiredStringFields: readonly (keyof T & string)[],
): (data: unknown) => data is T {
  return (data: unknown): data is T => {
    if (!isObjectRecord(data)) return false
    for (const key of requiredStringFields) {
      const value = (data as Record<string, unknown>)[key]
      // Reject whitespace-only strings as well as empty ones -- a
      // label like ``'   '`` would otherwise pass this guard and
      // surface as a blank name / role / id in the UI instead of
      // falling back to ``node.id`` via the outer code path.
      if (typeof value !== 'string' || value.trim().length === 0) return false
    }
    return true
  }
}

const isAgentNodeData = makeStringFieldGuard<AgentNodeData>([
  'agentId',
  'name',
  'role',
  'department',
  'level',
  'runtimeStatus',
])

const isDepartmentGroupData = makeStringFieldGuard<DepartmentGroupData>([
  'departmentName',
  'displayName',
])

const isOwnerNodeData = makeStringFieldGuard<OwnerNodeData>([
  'ownerId',
  'displayName',
  'role',
])

function getNodeLabel(node: Node): string {
  switch (node.type) {
    case 'agent':
    case 'ceo':
      return isAgentNodeData(node.data) ? node.data.name : node.id
    case 'department':
      return isDepartmentGroupData(node.data) ? node.data.displayName : node.id
    case 'owner':
      return isOwnerNodeData(node.data) ? node.data.displayName : node.id
    default:
      return node.id
  }
}

export interface ContextMenuState {
  nodeId: string
  nodeType: 'agent' | 'ceo' | 'department'
  position: { x: number; y: number }
}

export interface OrgChartSelectionResult {
  contextMenu: ContextMenuState | null
  setContextMenu: (menu: ContextMenuState | null) => void
  deleteConfirm: { nodeId: string; label: string } | null
  setDeleteConfirm: (value: { nodeId: string; label: string } | null) => void
  handleNodeContextMenu: (event: ReactMouseEvent, node: Node) => void
  handleNodeClick: (event: ReactMouseEvent, node: Node) => void
  handleViewDetails: (nodeId: string) => void
  handleDelete: (nodeId: string) => void
  confirmDelete: () => void
  handlePaneClick: () => void
}

export function useOrgChartSelection(displayNodes: Node[]): OrgChartSelectionResult {
  const navigate = useNavigate()
  const addToast = useToastStore((s) => s.add)

  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ nodeId: string; label: string } | null>(null)

  const handleNodeContextMenu = useCallback(
    (event: ReactMouseEvent, node: Node) => {
      event.preventDefault()
      if (!isValidNodeType(node.type)) return
      setContextMenu({
        nodeId: node.id,
        nodeType: node.type,
        position: { x: event.clientX, y: event.clientY },
      })
    },
    [],
  )

  const handleNodeClick = useCallback(
    (_event: ReactMouseEvent, node: Node) => {
      if (node.type === 'agent' || node.type === 'ceo') {
        navigate(`/agents/${encodeURIComponent(node.id)}`)
      }
    },
    [navigate],
  )

  const handleViewDetails = useCallback(
    (nodeId: string) => {
      const node = displayNodes.find((n) => n.id === nodeId)
      if (!node) return
      if (node.type === 'agent' || node.type === 'ceo') {
        navigate(`/agents/${encodeURIComponent(node.id)}`)
      }
    },
    [displayNodes, navigate],
  )

  const handleDelete = useCallback(
    (nodeId: string) => {
      const node = displayNodes.find((n) => n.id === nodeId)
      const label = node ? getNodeLabel(node).slice(0, 64) : nodeId
      setDeleteConfirm({ nodeId, label })
    },
    [displayNodes],
  )

  const confirmDelete = useCallback(() => {
    addToast({
      variant: 'info',
      title: 'Delete -- not yet available',
      description: 'Backend API for this operation is pending',
    })
    setDeleteConfirm(null)
  }, [addToast])

  const handlePaneClick = useCallback(() => {
    setContextMenu(null)
  }, [])

  return {
    contextMenu,
    setContextMenu,
    deleteConfirm,
    setDeleteConfirm,
    handleNodeContextMenu,
    handleNodeClick,
    handleViewDetails,
    handleDelete,
    confirmDelete,
    handlePaneClick,
  }
}
