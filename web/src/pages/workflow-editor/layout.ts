/**
 * Auto-layout workflow graphs using dagre.
 */

import dagre from '@dagrejs/dagre'
import type { Node, Edge } from '@xyflow/react'

const NODE_WIDTH = 180
const NODE_HEIGHT = 60
const TERMINAL_SIZE = 40

function getNodeDimensions(type: string | undefined): { width: number; height: number } {
  switch (type) {
    case 'start':
    case 'end':
      return { width: TERMINAL_SIZE, height: TERMINAL_SIZE }
    case 'conditional':
      return { width: 96, height: 96 }
    case 'parallel_split':
    case 'parallel_join':
      return { width: 140, height: 32 }
    default:
      return { width: NODE_WIDTH, height: NODE_HEIGHT }
  }
}

export function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'TB',
): Node[] {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: direction, nodesep: 60, ranksep: 80 })

  for (const node of nodes) {
    const dims = getNodeDimensions(node.type)
    g.setNode(node.id, { width: dims.width, height: dims.height })
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target)
  }

  dagre.layout(g)

  return nodes.map((node) => {
    const dagreNode = g.node(node.id)
    const dims = getNodeDimensions(node.type)
    return {
      ...node,
      position: {
        x: dagreNode.x - dims.width / 2,
        y: dagreNode.y - dims.height / 2,
      },
    }
  })
}
