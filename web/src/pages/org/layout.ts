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
const GROUP_NODE_HEADER_HEIGHT = 40
const EMPTY_GROUP_HEIGHT = 120 // matches DepartmentGroupNode min-h-[120px]

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
  const { direction = 'TB' } = options
  let { nodeSep = 60, rankSep = 100 } = options

  // Separate group nodes from leaf nodes
  const groupNodes = nodes.filter((n) => n.type === 'department')
  const leafNodes = nodes.filter((n) => n.type !== 'department')

  // Increase spacing to account for department group chrome (padding + header)
  if (groupNodes.length > 0) {
    nodeSep += DEFAULT_GROUP_PADDING * 2
    rankSep += GROUP_NODE_HEADER_HEIGHT + DEFAULT_GROUP_PADDING
  }

  if (leafNodes.length === 0) {
    // No agent nodes -- place department groups on a grid
    return nodes.map((n, i) => {
      const col = i % 3
      const row = Math.floor(i / 3)
      return { ...n, position: { x: col * 240, y: row * 160 }, style: { ...n.style, width: 200, height: EMPTY_GROUP_HEIGHT } }
    })
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
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
      g.setEdge(edge.source, edge.target)
    }
  }

  layout(g)

  // Map positioned leaf nodes (dagre returns center coords; React Flow uses top-left)
  const positionedLeafMap = new Map<string, Node>()
  for (const node of leafNodes) {
    const dagreNode = g.node(node.id) as { x: number; y: number; width: number; height: number }
    positionedLeafMap.set(node.id, {
      ...node,
      position: {
        x: dagreNode.x - dagreNode.width / 2,
        y: dagreNode.y - dagreNode.height / 2,
      },
    })
  }

  // Compute laid-out content bounds for offsetting empty groups
  let contentMaxX = 0
  let contentMaxY = 0
  for (const node of positionedLeafMap.values()) {
    const w = node.measured?.width ?? DEFAULT_NODE_WIDTH
    const h = node.measured?.height ?? DEFAULT_NODE_HEIGHT
    contentMaxX = Math.max(contentMaxX, node.position.x + w)
    contentMaxY = Math.max(contentMaxY, node.position.y + h)
  }

  // Compute group node positions and dimensions from their children,
  // then adjust children to group-relative positions (immutably)
  let emptyGroupIndex = 0
  const positionedGroups = groupNodes.map((group) => {
    const children = [...positionedLeafMap.values()].filter((n) => n.parentId === group.id)
    if (children.length === 0) {
      const xOffset = contentMaxX + DEFAULT_GROUP_PADDING * 2
      const col = emptyGroupIndex % 3
      const row = Math.floor(emptyGroupIndex / 3)
      emptyGroupIndex++
      return { ...group, position: { x: xOffset + col * 240, y: row * 160 }, style: { ...group.style, width: 200, height: EMPTY_GROUP_HEIGHT } }
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
    const groupY = minY - padding - GROUP_NODE_HEADER_HEIGHT
    const groupWidth = maxX - minX + padding * 2
    const groupHeight = maxY - minY + padding * 2 + GROUP_NODE_HEADER_HEIGHT

    // Make children positions relative to group (immutable update via map)
    for (const child of children) {
      positionedLeafMap.set(child.id, {
        ...child,
        position: {
          x: child.position.x - groupX,
          y: child.position.y - groupY,
        },
      })
    }

    return {
      ...group,
      position: { x: groupX, y: groupY },
      style: { ...group.style, width: groupWidth, height: groupHeight },
    }
  })

  return [...positionedGroups, ...positionedLeafMap.values()]
}
