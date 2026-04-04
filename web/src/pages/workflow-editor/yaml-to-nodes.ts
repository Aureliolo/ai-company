/**
 * Parse YAML workflow definition back into ReactFlow nodes and edges.
 *
 * Reverse of workflow-to-yaml.ts. Reconstructs the visual graph from
 * the flat step list format.
 *
 * Uses a two-pass approach:
 *   Pass 1 -- collect and validate all steps, build seenIds set
 *   Pass 2 -- emit edges only when both source and target exist
 */

import yaml from 'js-yaml'
import type { Node, Edge } from '@xyflow/react'
import type { WorkflowEdgeType } from '@/api/types'

export interface ParseResult {
  nodes: Node[]
  edges: Edge[]
  errors: string[]
  warnings: string[]
}

interface YamlStep {
  id?: string
  type?: string
  title?: string
  task_type?: string
  priority?: string
  complexity?: string
  coordination_topology?: string
  condition?: string
  branches?: string[]
  max_concurrency?: number
  join_strategy?: string
  strategy?: string
  role?: string
  agent_name?: string
  depends_on?: string[]
}

/** Validated step with a guaranteed id and type. */
interface ValidatedStep {
  id: string
  type: string
  step: YamlStep
  index: number
}

const VALID_TYPES = new Set([
  'task',
  'agent_assignment',
  'conditional',
  'parallel_split',
  'parallel_join',
])

const AUTO_LAYOUT_X = 250
const AUTO_LAYOUT_Y_START = 200
const AUTO_LAYOUT_Y_STEP = 120

/**
 * Map a backend edge type to the ReactFlow visual edge type used for
 * custom edge component selection.
 */
function edgeTypeToVisualType(edgeType: WorkflowEdgeType): string {
  if (edgeType === 'conditional_true' || edgeType === 'conditional_false') {
    return 'conditional'
  }
  return edgeType
}

/**
 * Infer the backend edge type for a depends_on edge based on the
 * source step's configuration.
 *
 * - If the source is a conditional node (has condition_expression),
 *   assigns 'conditional_true' for the first branch and
 *   'conditional_false' for the second.
 * - Otherwise returns 'sequential'.
 */
/**
 * Infer the edge type from the source step's type and branch index.
 *
 * NOTE: Conditional branch assignment (true vs false) is based on
 * declaration order in depends_on, which can flip if the user
 * reorders steps in YAML.  A future improvement would store
 * explicit branch metadata in the YAML schema (e.g.
 * `{ id: "stepA", branch: "true" }`).
 */
function inferDependsOnEdgeType(
  sourceStep: ValidatedStep,
  branchIndex: number,
): WorkflowEdgeType {
  if (sourceStep.type === 'conditional' && sourceStep.step.condition) {
    return branchIndex === 0 ? 'conditional_true' : 'conditional_false'
  }
  return 'sequential'
}

/**
 * Parse a YAML string into ReactFlow nodes and edges.
 *
 * @param yamlStr - YAML content to parse
 * @param existingPositions - Optional map of nodeId -> position for
 *   preserving layout when round-tripping
 */
export function parseYamlToNodesEdges(
  yamlStr: string,
  existingPositions?: Map<string, { x: number; y: number }>,
): ParseResult {
  const errors: string[] = []
  const warnings: string[] = []
  const nodes: Node[] = []
  const edges: Edge[] = []

  let parsed: unknown
  try {
    parsed = yaml.load(yamlStr, { schema: yaml.CORE_SCHEMA })
  } catch (err) {
    errors.push(`YAML parse error: ${err instanceof Error ? err.message : String(err)}`)
    return { nodes, edges, errors, warnings }
  }

  if (typeof parsed !== 'object' || parsed === null) {
    errors.push('YAML must contain an object')
    return { nodes, edges, errors, warnings }
  }

  const root = parsed as Record<string, unknown>
  const wfDef = root.workflow_definition as Record<string, unknown> | undefined
  if (!wfDef) {
    errors.push('Missing "workflow_definition" key')
    return { nodes, edges, errors, warnings }
  }

  const steps = wfDef.steps as YamlStep[] | undefined
  if (!Array.isArray(steps)) {
    errors.push('Missing or invalid "steps" array')
    return { nodes, edges, errors, warnings }
  }

  // ---------------------------------------------------------------
  // Pass 1: Collect and validate all steps, build seenIds + stepMap
  // ---------------------------------------------------------------
  const seenIds = new Set<string>()
  const stepMap = new Map<string, ValidatedStep>()
  let autoIdCounter = 0

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i] as YamlStep | undefined
    if (!step) continue
    const stepId = step.id ?? `auto-${++autoIdCounter}`

    if (!step.id) {
      warnings.push(`Step ${i + 1} has no id, auto-generated: ${stepId}`)
    }

    if (seenIds.has(stepId)) {
      errors.push(`Duplicate step id: ${stepId}`)
      continue
    }

    const stepType = step.type ?? 'task'
    if (!VALID_TYPES.has(stepType)) {
      warnings.push(`Unknown step type "${stepType}" for step ${stepId}, skipping`)
      continue
    }

    // Only add to seenIds after type validation passes
    seenIds.add(stepId)
    stepMap.set(stepId, { id: stepId, type: stepType, step, index: i })
  }

  // ---------------------------------------------------------------
  // Build nodes from validated steps
  // ---------------------------------------------------------------
  const startId = 'start-1'
  nodes.push({
    id: startId,
    type: 'start',
    position: existingPositions?.get(startId) ?? { x: AUTO_LAYOUT_X, y: 50 },
    data: { label: 'Start', config: {} },
  })

  const stepIds: string[] = []

  for (const [stepId, validated] of stepMap) {
    stepIds.push(stepId)
    const config = buildConfig(validated.step, validated.type)
    const position = existingPositions?.get(stepId) ?? {
      x: AUTO_LAYOUT_X,
      y: AUTO_LAYOUT_Y_START + validated.index * AUTO_LAYOUT_Y_STEP,
    }

    nodes.push({
      id: stepId,
      type: validated.type,
      position,
      data: { label: validated.step.title ?? stepId, config },
    })
  }

  // ---------------------------------------------------------------
  // Pass 2: Emit edges -- only when both source and target are valid
  // ---------------------------------------------------------------

  // Track how many depends_on edges each conditional source has
  // emitted so we can alternate true/false branches.
  const conditionalBranchCounters = new Map<string, number>()

  for (const [stepId, validated] of stepMap) {
    const { step } = validated

    // Edges from depends_on
    if (step.depends_on && Array.isArray(step.depends_on)) {
      for (const rawDepId of step.depends_on) {
        const depId = String(rawDepId)
        if (!seenIds.has(depId)) {
          errors.push(`Step '${stepId}' references unknown dependency '${depId}'`)
          continue
        }

        const sourceStep = stepMap.get(depId)!
        const branchIdx = conditionalBranchCounters.get(depId) ?? 0
        const edgeType = inferDependsOnEdgeType(sourceStep, branchIdx)

        if (sourceStep.type === 'conditional' && sourceStep.step.condition) {
          conditionalBranchCounters.set(depId, branchIdx + 1)
        }

        const visualType = edgeTypeToVisualType(edgeType)
        const isTrue = edgeType === 'conditional_true'
        const isFalse = edgeType === 'conditional_false'

        edges.push({
          id: `edge-${depId}-${stepId}`,
          source: depId,
          target: stepId,
          type: visualType,
          sourceHandle: isTrue ? 'true' : isFalse ? 'false' : undefined,
          data: {
            edgeType,
            branch: isTrue ? 'true' : isFalse ? 'false' : undefined,
          },
        })
      }
    }

    // Edges from branches (parallel_split)
    if (step.branches && Array.isArray(step.branches)) {
      for (const rawTarget of step.branches) {
        const branchTarget = String(rawTarget)
        if (!seenIds.has(branchTarget)) {
          errors.push(`Step '${stepId}' references unknown branch target '${branchTarget}'`)
          continue
        }

        const edgeType: WorkflowEdgeType = 'parallel_branch'
        edges.push({
          id: `edge-${stepId}-${branchTarget}`,
          source: stepId,
          target: branchTarget,
          type: edgeTypeToVisualType(edgeType),
          data: { edgeType },
        })
      }
    }
  }

  // ---------------------------------------------------------------
  // Synthetic end node
  // ---------------------------------------------------------------
  const endId = 'end-1'
  nodes.push({
    id: endId,
    type: 'end',
    position: existingPositions?.get(endId) ?? {
      x: AUTO_LAYOUT_X,
      y: AUTO_LAYOUT_Y_START + steps.length * AUTO_LAYOUT_Y_STEP,
    },
    data: { label: 'End', config: {} },
  })

  // ---------------------------------------------------------------
  // Connect start node to root steps (those with no incoming edges)
  // ---------------------------------------------------------------
  const hasIncoming = new Set(edges.map((e) => e.target))
  const rootStepIds = stepIds.filter((id) => !hasIncoming.has(id))

  for (const rootId of rootStepIds) {
    edges.push({
      id: `edge-${startId}-${rootId}`,
      source: startId,
      target: rootId,
      type: 'sequential',
      data: { edgeType: 'sequential' as WorkflowEdgeType },
    })
  }

  // Connect leaf steps (those with no outgoing edges) to end
  const hasOutgoing = new Set(edges.map((e) => e.source))
  for (const stepId of stepIds) {
    if (!hasOutgoing.has(stepId)) {
      edges.push({
        id: `edge-${stepId}-${endId}`,
        source: stepId,
        target: endId,
        type: 'sequential',
        data: { edgeType: 'sequential' as WorkflowEdgeType },
      })
    }
  }

  return { nodes, edges, errors, warnings }
}

function buildConfig(step: YamlStep, stepType: string): Record<string, unknown> {
  const config: Record<string, unknown> = {}

  if (stepType === 'task') {
    if (step.title) config.title = step.title
    if (step.task_type) config.task_type = step.task_type
    if (step.priority) config.priority = step.priority
    if (step.complexity) config.complexity = step.complexity
    if (step.coordination_topology) config.coordination_topology = step.coordination_topology
  } else if (stepType === 'conditional') {
    if (step.condition) config.condition_expression = step.condition
  } else if (stepType === 'parallel_split') {
    if (step.max_concurrency != null) config.max_concurrency = step.max_concurrency
  } else if (stepType === 'parallel_join') {
    config.join_strategy = step.join_strategy ?? 'all'
  } else if (stepType === 'agent_assignment') {
    if (step.strategy) config.routing_strategy = step.strategy
    if (step.role) config.role_filter = step.role
    if (step.agent_name) config.agent_name = step.agent_name
  }

  return config
}
