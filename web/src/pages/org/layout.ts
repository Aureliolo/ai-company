import { Graph, layout } from '@dagrejs/dagre'
import type { Node, Edge } from '@xyflow/react'

export type LayoutDirection = 'TB' | 'LR'

export interface LayoutOptions {
  direction?: LayoutDirection
  nodeSep?: number
  rankSep?: number
}

const DEFAULT_NODE_WIDTH = 160
const DEFAULT_NODE_HEIGHT = 80
const DEFAULT_GROUP_PADDING = 40

/**
 * Apply dagre hierarchical layout to React Flow nodes and edges.
 *
 * Returns a new array of nodes with `position` set. Edges are unchanged.
 * Group (department) nodes are excluded from dagre and sized to contain
 * their children after layout.
 */
export function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {},
): Node[] {
  const { direction = 'TB', nodeSep = 60, rankSep = 100 } = options

  // Separate group nodes from leaf nodes
  const groupNodes = nodes.filter((n) => n.type === 'department')
  const leafNodes = nodes.filter((n) => n.type !== 'department')

  if (leafNodes.length === 0) {
    return nodes.map((n) => ({ ...n, position: { x: 0, y: 0 } }))
  }

  // Build dagre graph from leaf nodes only
  const g = new Graph()
  g.setGraph({ rankdir: direction, nodesep: nodeSep, ranksep: rankSep })
  g.setDefaultEdgeLabel(() => ({}))

  for (const node of leafNodes) {
    g.setNode(node.id, {
      width: node.measured?.width ?? DEFAULT_NODE_WIDTH,
      height: node.measured?.height ?? DEFAULT_NODE_HEIGHT,
    })
  }

  for (const edge of edges) {
    // Only add edges between nodes that exist in the graph
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
      g.setEdge(edge.source, edge.target)
    }
  }

  layout(g)

  // Map positioned leaf nodes
  const positionedLeaves = leafNodes.map((node) => {
    const dagreNode = g.node(node.id) as { x: number; y: number; width: number; height: number }
    // Dagre returns center coordinates; React Flow uses top-left
    const position = {
      x: dagreNode.x - dagreNode.width / 2,
      y: dagreNode.y - dagreNode.height / 2,
    }

    // If the node has a parent group, make position relative to the group
    if (node.parentId) {
      return { ...node, position }
    }
    return { ...node, position }
  })

  // Compute group node positions and dimensions from their children
  const positionedGroups = groupNodes.map((group) => {
    const children = positionedLeaves.filter((n) => n.parentId === group.id)
    if (children.length === 0) {
      return { ...group, position: { x: 0, y: 0 }, style: { width: 200, height: 100 } }
    }

    const padding = DEFAULT_GROUP_PADDING
    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity

    for (const child of children) {
      const w = child.measured?.width ?? DEFAULT_NODE_WIDTH
      const h = child.measured?.height ?? DEFAULT_NODE_HEIGHT
      minX = Math.min(minX, child.position.x)
      minY = Math.min(minY, child.position.y)
      maxX = Math.max(maxX, child.position.x + w)
      maxY = Math.max(maxY, child.position.y + h)
    }

    const groupX = minX - padding
    const groupY = minY - padding - 40 // Extra space for header
    const groupWidth = maxX - minX + padding * 2
    const groupHeight = maxY - minY + padding * 2 + 40

    // Make children positions relative to group
    const adjustedChildren = positionedLeaves
      .filter((n) => n.parentId === group.id)
      .map((child) => ({
        ...child,
        position: {
          x: child.position.x - groupX,
          y: child.position.y - groupY,
        },
      }))

    // Update the leaves in-place for relative positioning
    for (const adj of adjustedChildren) {
      const idx = positionedLeaves.findIndex((n) => n.id === adj.id)
      if (idx !== -1) {
        positionedLeaves[idx] = adj
      }
    }

    return {
      ...group,
      position: { x: groupX, y: groupY },
      style: { ...group.style, width: groupWidth, height: groupHeight },
    }
  })

  return [...positionedGroups, ...positionedLeaves]
}
