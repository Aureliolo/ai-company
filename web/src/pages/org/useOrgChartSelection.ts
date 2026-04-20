import { useCallback, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import type { Node } from '@xyflow/react'
import { useNavigate } from 'react-router'
import { useToastStore } from '@/stores/toast'
import type { AgentNodeData, DepartmentGroupData, OwnerNodeData } from './build-org-tree'

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
