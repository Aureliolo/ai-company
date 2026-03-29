import { memo, useMemo } from 'react'
import { BaseEdge, getBezierPath, type EdgeProps, type Edge } from '@xyflow/react'
import { prefersReducedMotion } from '@/lib/motion'

export interface CommunicationEdgeData {
  /** Total message count for this edge. */
  volume: number
  /** Messages per hour -- used for animation speed scaling. */
  frequency: number
  /** Max volume across all edges -- used for relative scaling. */
  maxVolume: number
  [key: string]: unknown
}

export type CommunicationEdgeType = Edge<CommunicationEdgeData, 'communication'>

const MIN_STROKE_WIDTH = 1.5
const MAX_STROKE_WIDTH = 6
const MIN_OPACITY = 0.3
const MAX_OPACITY = 0.8
const MIN_DASH_DURATION = 0.5 // seconds (fast)
const MAX_DASH_DURATION = 4 // seconds (slow)

function CommunicationEdgeComponent(props: EdgeProps<CommunicationEdgeType>) {
  const { volume = 1, frequency = 1, maxVolume = 1 } = (props.data ?? {}) as CommunicationEdgeData

  const [edgePath] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition,
    targetPosition: props.targetPosition,
  })

  // Scale stroke width linearly with volume ratio
  const ratio = Math.min(volume / Math.max(maxVolume, 1), 1)
  const strokeWidth = MIN_STROKE_WIDTH + ratio * (MAX_STROKE_WIDTH - MIN_STROKE_WIDTH)
  const opacity = MIN_OPACITY + ratio * (MAX_OPACITY - MIN_OPACITY)

  // Animation duration: higher frequency = faster (shorter duration)
  const dashDuration = Math.min(
    MAX_DASH_DURATION,
    Math.max(MIN_DASH_DURATION, MAX_DASH_DURATION / Math.max(frequency, 0.1)),
  )

  const safeId = String(props.id).replace(/[^a-zA-Z0-9_-]/g, '_')
  const edgeId = `comm-dash-${safeId}`

  const reduced = prefersReducedMotion()

  const style = useMemo(
    () => ({
      stroke: 'var(--color-accent)',
      strokeWidth,
      strokeOpacity: opacity,
      strokeDasharray: '8 4',
      ...(reduced ? {} : { animation: `${edgeId} ${dashDuration}s linear infinite` }),
    }),
    [strokeWidth, opacity, dashDuration, edgeId, reduced],
  )

  return (
    <>
      <style>{`@keyframes ${edgeId} { to { stroke-dashoffset: -24; } }`}</style>
      <BaseEdge id={props.id} path={edgePath} style={style} />
    </>
  )
}

export const CommunicationEdge = memo(CommunicationEdgeComponent)
