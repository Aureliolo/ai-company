import { useLayoutEffect, useReducer, useRef, useState } from 'react'
import type { Edge, Node } from '@xyflow/react'
import { createLogger } from '@/lib/logger'
import { prefersReducedMotion, TRANSITION_SLOW_MS } from '@/lib/motion'
import type { ViewMode } from './OrgChartToolbar'

const log = createLogger('OrgChart:ViewMode')
const TRANSITION_DURATION_MS = TRANSITION_SLOW_MS

function tweenSlowEase(t: number): number {
  if (t <= 0) return 0
  if (t >= 1) return 1
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
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

export interface OrgChartViewModeResult {
  viewMode: ViewMode
  setViewMode: (mode: ViewMode) => void
  displayNodes: Node[]
  displayEdges: Edge[]
  transitioning: boolean
}

/**
 * Owns the view mode (hierarchy/force) selector and the animated transition
 * between node layouts when switching modes. Uses a reducer + layout effect
 * so the first paint never shows a mid-transition state.
 */
export function useOrgChartViewMode(nodes: Node[], edges: Edge[]): OrgChartViewModeResult {
  const [viewMode, setViewMode] = useState<ViewMode>('hierarchy')
  const [transition, dispatch] = useReducer(transitionReducer, {
    displayNodes: [],
    displayEdges: [],
    transitioning: false,
  })
  const prevNodesRef = useRef<Node[]>([])
  const animFrameRef = useRef<number | null>(null)

  useLayoutEffect(() => {
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }

    const fromNodes = transition.displayNodes.length > 0 ? transition.displayNodes : prevNodesRef.current

    if (nodes.length === 0 || prefersReducedMotion() || fromNodes.length === 0) {
      prevNodesRef.current = nodes
      dispatch({ type: 'snap', nodes, edges })
      return
    }

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

  useLayoutEffect(() => {
    log.debug('Transition state', {
      nodes: nodes.length,
      edges: edges.length,
      displayNodes: transition.displayNodes.length,
      transitioning: transition.transitioning,
    })
  }, [nodes.length, edges.length, transition.displayNodes.length, transition.transitioning])

  return {
    viewMode,
    setViewMode,
    displayNodes: transition.displayNodes,
    displayEdges: transition.displayEdges,
    transitioning: transition.transitioning,
  }
}
