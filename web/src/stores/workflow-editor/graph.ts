import { applyEdgeChanges, applyNodeChanges, type Edge, type Node } from '@xyflow/react'
import { generateEdgeId, generateNodeId, nodeTypeToEdgeType, regenerateYaml } from './yaml'
import { MAX_UNDO, type GraphSlice, type SliceCreator, type WorkflowSnapshot } from './types'

export const createGraphSlice: SliceCreator<GraphSlice> = (set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  dirty: false,
  yamlPreview: '',

  addNode: (type, position) => {
    const { nodes, edges, definition } = get()
    const snapshot: WorkflowSnapshot = {
      nodes: structuredClone(nodes),
      edges: structuredClone(edges),
    }
    const id = generateNodeId()
    const label = type.charAt(0).toUpperCase() + type.slice(1).replaceAll('_', ' ')
    const newNode: Node = { id, type, position, data: { label, config: {} } }
    const newNodes = [...nodes, newNode]
    const yaml = regenerateYaml(newNodes, edges, definition)
    set((s) => ({
      nodes: newNodes,
      dirty: true,
      undoStack: [...s.undoStack.slice(-MAX_UNDO + 1), snapshot],
      redoStack: [],
      yamlPreview: yaml,
    }))
  },

  updateNodeConfig: (nodeId, config) => {
    const { nodes, edges, definition } = get()
    const snapshot: WorkflowSnapshot = {
      nodes: structuredClone(nodes),
      edges: structuredClone(edges),
    }
    const newNodes = nodes.map((n) =>
      n.id === nodeId
        ? { ...n, data: { ...(n.data as Record<string, unknown>), config } }
        : n,
    )
    const yaml = regenerateYaml(newNodes, edges, definition)
    set((s) => ({
      nodes: newNodes,
      dirty: true,
      undoStack: [...s.undoStack.slice(-MAX_UNDO + 1), snapshot],
      redoStack: [],
      yamlPreview: yaml,
    }))
  },

  removeNode: (nodeId) => {
    const { nodes, edges, definition } = get()
    const snapshot: WorkflowSnapshot = {
      nodes: structuredClone(nodes),
      edges: structuredClone(edges),
    }
    const newNodes = nodes.filter((n) => n.id !== nodeId)
    const newEdges = edges.filter((e) => e.source !== nodeId && e.target !== nodeId)
    const yaml = regenerateYaml(newNodes, newEdges, definition)
    set((s) => ({
      nodes: newNodes,
      edges: newEdges,
      dirty: true,
      selectedNodeId: s.selectedNodeId === nodeId ? null : s.selectedNodeId,
      undoStack: [...s.undoStack.slice(-MAX_UNDO + 1), snapshot],
      redoStack: [],
      yamlPreview: yaml,
    }))
  },

  onConnect: (connection) => {
    const { nodes, edges, definition } = get()
    if (!connection.source || !connection.target) return
    const snapshot: WorkflowSnapshot = {
      nodes: structuredClone(nodes),
      edges: structuredClone(edges),
    }
    const sourceNode = nodes.find((n) => n.id === connection.source)
    const edgeType = nodeTypeToEdgeType(sourceNode?.type)
    const isTrueBranch = connection.sourceHandle === 'true'
    const newEdge: Edge = {
      id: generateEdgeId(),
      source: connection.source,
      target: connection.target,
      type: edgeType,
      sourceHandle: connection.sourceHandle ?? undefined,
      targetHandle: connection.targetHandle ?? undefined,
      data: {
        edgeType: sourceNode?.type === 'conditional'
          ? (isTrueBranch ? 'conditional_true' : 'conditional_false')
          : sourceNode?.type === 'parallel_split'
            ? 'parallel_branch'
            : 'sequential',
        branch: sourceNode?.type === 'conditional' ? (isTrueBranch ? 'true' : 'false') : undefined,
      },
    }
    const newEdges = [...edges, newEdge]
    const yaml = regenerateYaml(nodes, newEdges, definition)
    set((s) => ({
      edges: newEdges,
      dirty: true,
      undoStack: [...s.undoStack.slice(-MAX_UNDO + 1), snapshot],
      redoStack: [],
      yamlPreview: yaml,
    }))
  },

  removeEdge: (edgeId) => {
    const { nodes, edges, definition } = get()
    const snapshot: WorkflowSnapshot = {
      nodes: structuredClone(nodes),
      edges: structuredClone(edges),
    }
    const newEdges = edges.filter((e) => e.id !== edgeId)
    const yaml = regenerateYaml(nodes, newEdges, definition)
    set((s) => ({
      edges: newEdges,
      dirty: true,
      undoStack: [...s.undoStack.slice(-MAX_UNDO + 1), snapshot],
      redoStack: [],
      yamlPreview: yaml,
    }))
  },

  onNodesChange: (changes) => {
    set((s) => {
      const hasMoves = changes.some((c) => c.type === 'position' || c.type === 'remove')
      const snapshot = hasMoves
        ? { nodes: structuredClone(s.nodes), edges: structuredClone(s.edges) }
        : null
      const newNodes = applyNodeChanges(changes, s.nodes)
      return {
        nodes: newNodes,
        dirty: s.dirty || hasMoves,
        yamlPreview: hasMoves ? regenerateYaml(newNodes, s.edges, s.definition) : s.yamlPreview,
        undoStack: snapshot ? [...s.undoStack.slice(-MAX_UNDO + 1), snapshot] : s.undoStack,
        redoStack: snapshot ? [] : s.redoStack,
      }
    })
  },

  onEdgesChange: (changes) => {
    set((s) => {
      const hasRemoves = changes.some((c) => c.type === 'remove')
      const snapshot = hasRemoves
        ? { nodes: structuredClone(s.nodes), edges: structuredClone(s.edges) }
        : null
      const newEdges = applyEdgeChanges(changes, s.edges)
      return {
        edges: newEdges,
        dirty: s.dirty || hasRemoves,
        yamlPreview: hasRemoves ? regenerateYaml(s.nodes, newEdges, s.definition) : s.yamlPreview,
        undoStack: snapshot ? [...s.undoStack.slice(-MAX_UNDO + 1), snapshot] : s.undoStack,
        redoStack: snapshot ? [] : s.redoStack,
      }
    })
  },

  selectNode: (nodeId) => {
    set({ selectedNodeId: nodeId })
  },
})
