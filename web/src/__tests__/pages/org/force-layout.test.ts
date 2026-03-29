import { describe, expect, it } from 'vitest'
import type { Node } from '@xyflow/react'
import { computeForceLayout } from '@/pages/org/force-layout'
import type { CommunicationLink } from '@/pages/org/aggregate-messages'

function makeNode(id: string, x = 0, y = 0): Node {
  return { id, position: { x, y }, data: {} }
}

function makeLink(source: string, target: string, volume = 1, frequency = 1): CommunicationLink {
  return { source, target, volume, frequency }
}

describe('computeForceLayout', () => {
  it('returns empty array for empty input', () => {
    expect(computeForceLayout([], [])).toEqual([])
  })

  it('returns a single node with finite position', () => {
    const nodes = [makeNode('a')]
    const result = computeForceLayout(nodes, [])
    expect(result).toHaveLength(1)
    expect(Number.isFinite(result[0]!.position.x)).toBe(true)
    expect(Number.isFinite(result[0]!.position.y)).toBe(true)
  })

  it('positions two connected nodes at finite, separated coordinates', () => {
    const nodes = [makeNode('a'), makeNode('b', 100, 0)]
    const links = [makeLink('a', 'b')]
    const result = computeForceLayout(nodes, links)

    expect(result).toHaveLength(2)
    const [nodeA, nodeB] = result
    expect(Number.isFinite(nodeA!.position.x)).toBe(true)
    expect(Number.isFinite(nodeB!.position.x)).toBe(true)

    // Nodes should not overlap (be at least some distance apart)
    const dx = nodeA!.position.x - nodeB!.position.x
    const dy = nodeA!.position.y - nodeB!.position.y
    const distance = Math.sqrt(dx * dx + dy * dy)
    expect(distance).toBeGreaterThan(10)
  })

  it('all returned positions are finite numbers', () => {
    const nodes = [makeNode('a'), makeNode('b', 50, 0), makeNode('c', 0, 50)]
    const links = [makeLink('a', 'b'), makeLink('b', 'c')]
    const result = computeForceLayout(nodes, links)

    for (const node of result) {
      expect(Number.isFinite(node.position.x)).toBe(true)
      expect(Number.isFinite(node.position.y)).toBe(true)
    }
  })

  it('preserves node IDs and data', () => {
    const nodes = [
      { ...makeNode('a'), data: { name: 'Alice' } },
      { ...makeNode('b'), data: { name: 'Bob' } },
    ]
    const result = computeForceLayout(nodes, [makeLink('a', 'b')])

    expect(result.find((n) => n.id === 'a')!.data).toEqual({ name: 'Alice' })
    expect(result.find((n) => n.id === 'b')!.data).toEqual({ name: 'Bob' })
  })

  it('handles disconnected nodes without overlap', () => {
    const nodes = [makeNode('a'), makeNode('b', 10, 0), makeNode('c', 20, 0)]
    // No links -- all nodes are disconnected
    const result = computeForceLayout(nodes, [])

    // Each pair should have some distance due to repulsion
    for (let i = 0; i < result.length; i++) {
      for (let j = i + 1; j < result.length; j++) {
        const dx = result[i]!.position.x - result[j]!.position.x
        const dy = result[i]!.position.y - result[j]!.position.y
        const distance = Math.sqrt(dx * dx + dy * dy)
        expect(distance).toBeGreaterThan(5)
      }
    }
  })

  it('is deterministic (same input produces same output)', () => {
    const nodes = [makeNode('a', 0, 0), makeNode('b', 100, 0), makeNode('c', 50, 100)]
    const links = [makeLink('a', 'b', 5), makeLink('b', 'c', 3)]

    const result1 = computeForceLayout(nodes, links)
    const result2 = computeForceLayout(nodes, links)

    for (let i = 0; i < result1.length; i++) {
      expect(result1[i]!.position.x).toBeCloseTo(result2[i]!.position.x, 5)
      expect(result1[i]!.position.y).toBeCloseTo(result2[i]!.position.y, 5)
    }
  })

  it('higher-volume links place nodes closer together', () => {
    // A-B have high volume, A-C have low volume
    const nodes = [makeNode('a', 0, 0), makeNode('b', 200, 0), makeNode('c', 0, 200)]
    const links = [
      makeLink('a', 'b', 50, 10),
      makeLink('a', 'c', 1, 0.5),
    ]
    const result = computeForceLayout(nodes, links)

    const a = result.find((n) => n.id === 'a')!
    const b = result.find((n) => n.id === 'b')!
    const c = result.find((n) => n.id === 'c')!

    const distAB = Math.sqrt((a.position.x - b.position.x) ** 2 + (a.position.y - b.position.y) ** 2)
    const distAC = Math.sqrt((a.position.x - c.position.x) ** 2 + (a.position.y - c.position.y) ** 2)

    // High-volume pair A-B should be closer than low-volume pair A-C
    expect(distAB).toBeLessThan(distAC)
  })

  it('respects width and height options for centering', () => {
    const nodes = [makeNode('a'), makeNode('b', 100, 0)]
    const links = [makeLink('a', 'b')]
    const result = computeForceLayout(nodes, links, { width: 800, height: 600 })

    // Nodes should be roughly centered around (400, 300)
    const avgX = result.reduce((sum, n) => sum + n.position.x, 0) / result.length
    const avgY = result.reduce((sum, n) => sum + n.position.y, 0) / result.length
    expect(avgX).toBeGreaterThan(200)
    expect(avgX).toBeLessThan(600)
    expect(avgY).toBeGreaterThan(100)
    expect(avgY).toBeLessThan(500)
  })

  it('handles links referencing non-existent nodes gracefully', () => {
    const nodes = [makeNode('a'), makeNode('b')]
    const links = [makeLink('a', 'b'), makeLink('a', 'missing')]
    const result = computeForceLayout(nodes, links)

    expect(result).toHaveLength(2)
    for (const node of result) {
      expect(Number.isFinite(node.position.x)).toBe(true)
      expect(Number.isFinite(node.position.y)).toBe(true)
    }
  })
})
