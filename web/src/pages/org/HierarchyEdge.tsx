import { memo } from 'react'
import { BaseEdge, type Edge, type EdgeProps } from '@xyflow/react'
import { useReducedMotion } from 'motion/react'

export interface HierarchyEdgeData {
  /** When omitted or false, the edge renders as a static line. */
  particlesVisible?: boolean
  // React Flow requires data to extend Record<string, unknown>.
  [key: string]: unknown
}

type HierarchyEdgeType = Edge<HierarchyEdgeData, 'hierarchy'>

/** Target particle speed, in pixels per second. */
const PARTICLE_PX_PER_SEC = 140
/** Minimum duration for very short edges so the particle stays visible. */
const MIN_PARTICLE_DUR_SEC = 0.8
/**
 * Fixed horizontal bend offset below the source handle.  Every
 * edge with the same source Y will bend at the same absolute Y
 * coordinate, so when multiple edges fan out from a common parent
 * (Executive → Product + Engineering + Security) their horizontal
 * segments overlap into a single clean T-junction instead of
 * stacking as three independent Z-shapes.
 */
const BEND_OFFSET = 30

/**
 * Custom orthogonal hierarchy edge used for every reporting-chain
 * line in the org chart.
 *
 * We deliberately do NOT use React Flow's `getSmoothStepPath`
 * because its fanout routing is a Z-shape (`source → down @
 * sourceGapped.y → across @ centerX → down @ targetGapped.y →
 * across → target`) that picks a different Y for each sibling
 * edge, so three children of the same parent end up with three
 * mismatched horizontal segments instead of a single shared
 * junction line.  See:
 *   node_modules/@xyflow/system/.../index.mjs → `getPoints`
 *
 * Instead we compute a minimal L-shape path ourselves:
 *
 *     M sx sy          (start at source handle)
 *     L sx bendY       (drop straight down by BEND_OFFSET)
 *     L tx bendY       (horizontal across to target's x)
 *     L tx ty          (drop straight down to target handle)
 *
 * Every sibling edge with the same source Y draws its horizontal
 * segment at the identical `bendY = sourceY + BEND_OFFSET`, so the
 * three segments overlap perfectly and read as a single clean
 * T-junction under the parent.
 */
function HierarchyEdgeComponent(props: EdgeProps<HierarchyEdgeType>) {
  const reducedMotion = useReducedMotion()
  const showParticles = !reducedMotion && (props.data?.particlesVisible ?? false)

  const sx = props.sourceX
  const sy = props.sourceY
  const tx = props.targetX
  const ty = props.targetY
  const bendY = sy + BEND_OFFSET

  // Custom L-shape path.  If the horizontal delta is zero (source
  // and target perfectly aligned) we collapse to a straight vertical
  // drop to avoid emitting a redundant zero-length L segment.
  const edgePath =
    Math.abs(tx - sx) < 0.5
      ? `M${sx},${sy} L${tx},${ty}`
      : `M${sx},${sy} L${sx},${bendY} L${tx},${bendY} L${tx},${ty}`

  // Approximate path length (Manhattan distance) for uniform
  // particle speed across edges of different lengths.
  const approxLength = Math.abs(tx - sx) < 0.5
    ? Math.abs(ty - sy)
    : Math.abs(tx - sx) + Math.abs(ty - sy) + BEND_OFFSET
  const durSec = Math.max(MIN_PARTICLE_DUR_SEC, approxLength / PARTICLE_PX_PER_SEC)

  return (
    <>
      <BaseEdge
        id={props.id}
        path={edgePath}
        style={{
          stroke: 'var(--color-border-bright)',
          strokeWidth: 1.5,
          opacity: 0.7,
        }}
      />
      {showParticles && (
        <circle
          r="2.5"
          fill="var(--color-accent)"
          opacity="0.9"
          aria-hidden="true"
        >
          <animateMotion
            dur={`${durSec.toFixed(2)}s`}
            repeatCount="indefinite"
            path={edgePath}
          />
        </circle>
      )}
    </>
  )
}

export const HierarchyEdge = memo(HierarchyEdgeComponent)
