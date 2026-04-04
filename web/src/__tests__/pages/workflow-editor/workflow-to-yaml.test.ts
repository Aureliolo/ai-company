/**
 * Tests for workflow-to-YAML exporter (depends_on branch metadata).
 */
import { describe, it, expect } from 'vitest'
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
    const yaml = generateYamlPreview(nodes, edges, 'test', 'agile')
    // Parse back to verify depends_on is a plain string
    expect(yaml).toContain('depends_on')
    expect(yaml).toContain('- step_a')
    // Should NOT contain { id: ... } format
    expect(yaml).not.toContain('branch:')
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
    const yaml = generateYamlPreview(nodes, edges, 'test', 'agile')
    // Should contain branch metadata for conditional edges
    expect(yaml).toContain('branch:')
    expect(yaml).toMatch(/id:\s*check/)
    expect(yaml).toMatch(/branch:\s*['"]true['"]/)
    expect(yaml).toMatch(/branch:\s*['"]false['"]/)
  })

  it('emits plain string for parallel_branch edges (no branch metadata)', () => {
    const nodes = [
      makeNode('start', 'start'),
      makeNode('fork', 'parallel_branch'),
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
    const yaml = generateYamlPreview(nodes, edges, 'test', 'agile')
    // parallel_branch edges should emit plain string depends_on
    expect(yaml).not.toContain('branch:')
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
    const yaml = generateYamlPreview(nodes, edges, 'test', 'agile')
    // 'run' should have depends_on with { id: check, branch: true }
    expect(yaml).toContain('branch:')
  })
})
