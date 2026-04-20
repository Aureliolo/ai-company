import { useCallback, useMemo, useState } from 'react'
import type { Edge, EdgeMouseHandler } from '@xyflow/react'

export interface OrgChartEdgeInteractionResult {
  /** Edge currently hovered by the pointer, or `null` when none. */
  hoveredEdgeId: string | null
  /** Edges enriched with a `hovered` data flag for consumption by edge components. */
  edgesWithHoverState: Edge[]
  onEdgeMouseEnter: EdgeMouseHandler
  onEdgeMouseLeave: EdgeMouseHandler
  onEdgeClick: EdgeMouseHandler
}

interface UseOrgChartEdgeInteractionArgs {
  edges: readonly Edge[]
  onEdgeSelected?: (edge: Edge) => void
}

/**
 * Tracks pointer hover over org-chart edges and exposes ReactFlow-compatible
 * handlers plus an `edgesWithHoverState` array that mirrors the input edges
 * with a `hovered: boolean` flag on `data`. Edge components can read
 * `data.hovered` to change stroke weight/colour without re-subscribing the
 * whole graph. Click selection is optional and routed via `onEdgeSelected`.
 */
export function useOrgChartEdgeInteraction(
  args: UseOrgChartEdgeInteractionArgs,
): OrgChartEdgeInteractionResult {
  const { edges, onEdgeSelected } = args
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null)

  const onEdgeMouseEnter = useCallback<EdgeMouseHandler>((_, edge) => {
    setHoveredEdgeId(edge.id)
  }, [])

  const onEdgeMouseLeave = useCallback<EdgeMouseHandler>((_, edge) => {
    setHoveredEdgeId((current) => (current === edge.id ? null : current))
  }, [])

  const onEdgeClick = useCallback<EdgeMouseHandler>(
    (_, edge) => {
      onEdgeSelected?.(edge)
    },
    [onEdgeSelected],
  )

  const edgesWithHoverState = useMemo(() => {
    if (hoveredEdgeId === null) return [...edges]
    return edges.map((edge) => {
      if (edge.id !== hoveredEdgeId) return edge
      return { ...edge, data: { ...(edge.data as Record<string, unknown> | undefined), hovered: true } }
    })
  }, [edges, hoveredEdgeId])

  return {
    hoveredEdgeId,
    edgesWithHoverState,
    onEdgeMouseEnter,
    onEdgeMouseLeave,
    onEdgeClick,
  }
}
