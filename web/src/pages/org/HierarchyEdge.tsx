import { memo } from 'react'
import { BaseEdge, getSmoothStepPath, type EdgeProps } from '@xyflow/react'

function HierarchyEdgeComponent(props: EdgeProps) {
  const [edgePath] = getSmoothStepPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition,
    targetPosition: props.targetPosition,
    borderRadius: 8,
  })

  return (
    <BaseEdge
      id={props.id}
      path={edgePath}
      style={{
        stroke: 'var(--color-border-bright)',
        strokeWidth: 1.5,
      }}
    />
  )
}

export const HierarchyEdge = memo(HierarchyEdgeComponent)
