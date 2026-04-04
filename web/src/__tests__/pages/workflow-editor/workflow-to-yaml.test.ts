/**
 * Tests for workflow-to-YAML exporter (depends_on branch metadata).
 */
import { describe, it, expect } from 'vitest'
import yaml from 'js-yaml'
import type { Node, Edge } from '@xyflow/react'
import { generateYamlPreview } from '@/pages/workflow-editor/workflow-to-yaml'

function makeNode(id: string, type: string, config?: Record<string, unknown>): Node {
  return {
    id,
    type,
    position: { x: 0, y: 0 },
    data: { label: id, config: config ?? {} },
  }
}

function makeEdge(
  source: string,
  target: string,
  edgeType: string = 'sequential',
  branch?: 'true' | 'false',
): Edge {
  return {
    id: `edge-${source}-${target}`,
    source,
    target,
    type: edgeType === 'sequential' ? 'sequential' : 'conditional',
    data: { edgeType, branch },
  }
}

describe('generateYamlPreview depends_on', () => {
  it('emits plain string for sequential edges', () => {
    const nodes = [
      makeNode('start', 'start'),
      makeNode('step_a', 'task', { title: 'A' }),
      makeNode('step_b', 'task', { title: 'B' }),
      makeNode('end', 'end'),
    ]
    const edges = [
      makeEdge('start', 'step_a'),
      makeEdge('step_a', 'step_b'),
      makeEdge('step_b', 'end'),
    ]
    const output = generateYamlPreview(nodes, edges, 'test', 'agile')
    // Parse back to verify depends_on is a plain string
    expect(output).toContain('depends_on')
    expect(output).toContain('- step_a')
    // Should NOT contain { id: ... } format
    expect(output).not.toContain('branch:')
  })

  it('emits object with branch for conditional edges', () => {
    const nodes = [
      makeNode('start', 'start'),
      makeNode('check', 'conditional', { condition_expression: 'env == prod' }),
      makeNode('yes_step', 'task', { title: 'Yes' }),
      makeNode('no_step', 'task', { title: 'No' }),
      makeNode('end', 'end'),
    ]
    const edges = [
      makeEdge('start', 'check'),
      makeEdge('check', 'yes_step', 'conditional_true', 'true'),
      makeEdge('check', 'no_step', 'conditional_false', 'false'),
      makeEdge('yes_step', 'end'),
      makeEdge('no_step', 'end'),
    ]
    const output = generateYamlPreview(nodes, edges, 'test', 'agile')
    // Parse the YAML and assert on the depends_on structure directly
    const parsed = yaml.load(output, { schema: yaml.CORE_SCHEMA }) as Record<string, unknown>
    const steps = (parsed as { workflow_definition: { steps: Array<Record<string, unknown>> } }).workflow_definition.steps
    const yesStep = steps.find((s) => s.id === 'yes_step')
    const noStep = steps.find((s) => s.id === 'no_step')
    expect(yesStep).toBeDefined()
    expect(noStep).toBeDefined()
    expect(yesStep!.depends_on).toEqual([{ id: 'check', branch: 'true' }])
    expect(noStep!.depends_on).toEqual([{ id: 'check', branch: 'false' }])
  })

  it('emits branches field for parallel_split node (no branch metadata in depends_on)', () => {
    const nodes = [
      makeNode('start', 'start'),
      makeNode('fork', 'parallel_split'),
      makeNode('a', 'task', { title: 'A' }),
      makeNode('b', 'task', { title: 'B' }),
      makeNode('end', 'end'),
    ]
    const edges = [
      makeEdge('start', 'fork'),
      makeEdge('fork', 'a', 'parallel_branch'),
      makeEdge('fork', 'b', 'parallel_branch'),
      makeEdge('a', 'end'),
      makeEdge('b', 'end'),
    ]
    const output = generateYamlPreview(nodes, edges, 'test', 'agile')
    const parsed = yaml.load(output, { schema: yaml.CORE_SCHEMA }) as Record<string, unknown>
    const steps = (parsed as { workflow_definition: { steps: Array<Record<string, unknown>> } }).workflow_definition.steps
    // The split node should have a branches field listing targets
    const forkStep = steps.find((s) => s.id === 'fork')
    expect(forkStep).toBeDefined()
    expect(forkStep!.branches).toEqual(expect.arrayContaining(['a', 'b']))
    // Child tasks should have plain string depends_on (no branch metadata)
    const aStep = steps.find((s) => s.id === 'a')
    expect(aStep).toBeDefined()
    expect(aStep!.depends_on).toEqual(['fork'])
    expect(output).not.toContain('branch:')
  })

  it('emits mixed plain strings and objects when both edge types exist', () => {
    const nodes = [
      makeNode('start', 'start'),
      makeNode('setup', 'task', { title: 'Setup' }),
      makeNode('check', 'conditional', { condition_expression: 'ready' }),
      makeNode('run', 'task', { title: 'Run' }),
      makeNode('end', 'end'),
    ]
    const edges = [
      makeEdge('start', 'setup'),
      makeEdge('setup', 'check'),
      makeEdge('check', 'run', 'conditional_true', 'true'),
      makeEdge('run', 'end'),
    ]
    const output = generateYamlPreview(nodes, edges, 'test', 'agile')
    const parsed = yaml.load(output, { schema: yaml.CORE_SCHEMA }) as Record<string, unknown>
    const steps = (parsed as { workflow_definition: { steps: Array<Record<string, unknown>> } }).workflow_definition.steps
    // 'run' should have depends_on with { id: check, branch: 'true' }
    const runStep = steps.find((s) => s.id === 'run')
    expect(runStep).toBeDefined()
    expect(runStep!.depends_on).toEqual([{ id: 'check', branch: 'true' }])
    // 'check' should have plain string depends_on from setup
    const checkStep = steps.find((s) => s.id === 'check')
    expect(checkStep).toBeDefined()
    expect(checkStep!.depends_on).toEqual(['setup'])
  })
})
