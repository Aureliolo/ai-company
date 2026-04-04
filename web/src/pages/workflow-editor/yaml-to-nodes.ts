/**
 * Parse YAML workflow definition back into ReactFlow nodes and edges.
 *
 * Reverse of workflow-to-yaml.ts. Reconstructs the visual graph from
 * the flat step list format.
 */

import yaml from 'js-yaml'
import type { Node, Edge } from '@xyflow/react'

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

  // Check for duplicate IDs
  const seenIds = new Set<string>()
  let autoIdCounter = 0

  // Add synthetic start node
  const startId = 'start-1'
  nodes.push({
    id: startId,
    type: 'start',
    position: existingPositions?.get(startId) ?? { x: AUTO_LAYOUT_X, y: 50 },
    data: { label: 'Start', config: {} },
  })

  // Track first step for connecting start node
  let firstStepId: string | null = null
  const stepIds: string[] = []

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
    seenIds.add(stepId)

    const stepType = step.type ?? 'task'
    if (!VALID_TYPES.has(stepType)) {
      warnings.push(`Unknown step type "${stepType}" for step ${stepId}, skipping`)
      continue
    }

    if (firstStepId === null) firstStepId = stepId
    stepIds.push(stepId)

    // Build node config from step fields
    const config = buildConfig(step, stepType)

    const position = existingPositions?.get(stepId) ?? {
      x: AUTO_LAYOUT_X,
      y: AUTO_LAYOUT_Y_START + i * AUTO_LAYOUT_Y_STEP,
    }

    nodes.push({
      id: stepId,
      type: stepType,
      position,
      data: { label: step.title ?? stepId, config },
    })

    // Build edges from depends_on
    if (step.depends_on && Array.isArray(step.depends_on)) {
      for (const depId of step.depends_on) {
        const edgeType = inferEdgeType()
        edges.push({
          id: `edge-${depId}-${stepId}`,
          source: depId,
          target: stepId,
          type: edgeType === 'sequential' ? 'sequential' : 'conditional',
          data: { edgeType },
        })
      }
    }

    // Build edges from branches (parallel_split)
    if (step.branches && Array.isArray(step.branches)) {
      for (const branchTarget of step.branches) {
        edges.push({
          id: `edge-${stepId}-${branchTarget}`,
          source: stepId,
          target: branchTarget,
          type: 'sequential',
          data: { edgeType: 'parallel_branch' },
        })
      }
    }
  }

  // Add synthetic end node
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

  // Connect start to first step
  if (firstStepId) {
    edges.push({
      id: `edge-${startId}-${firstStepId}`,
      source: startId,
      target: firstStepId,
      type: 'sequential',
      data: { edgeType: 'sequential' },
    })
  }

  // Connect last step(s) without outgoing edges to end
  const hasOutgoing = new Set(edges.map((e) => e.source))
  for (const stepId of stepIds) {
    if (!hasOutgoing.has(stepId)) {
      edges.push({
        id: `edge-${stepId}-${endId}`,
        source: stepId,
        target: endId,
        type: 'sequential',
        data: { edgeType: 'sequential' },
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

/**
 * Infer edge type -- defaults to sequential since conditional edge
 * types are resolved at render time by the editor.
 */
function inferEdgeType(): string {
  return 'sequential'
}
