import type { SliceCreator, UndoRedoSlice, WorkflowSnapshot } from './types'
import { regenerateYaml } from './yaml'

export const createUndoRedoSlice: SliceCreator<UndoRedoSlice> = (set, get) => ({
  undoStack: [],
  redoStack: [],

  undo: () => {
    const { undoStack, nodes, edges, definition } = get()
    if (undoStack.length === 0) return
    const snapshot = undoStack.at(-1)
    if (!snapshot) return
    const current: WorkflowSnapshot = { nodes: structuredClone(nodes), edges: structuredClone(edges) }
    const restoredNodes = structuredClone(snapshot.nodes)
    const restoredEdges = structuredClone(snapshot.edges)
    const yaml = regenerateYaml(restoredNodes, restoredEdges, definition)
    set({
      nodes: restoredNodes,
      edges: restoredEdges,
      undoStack: undoStack.slice(0, -1),
      redoStack: [...get().redoStack, current],
      dirty: true,
      yamlPreview: yaml,
    })
  },

  redo: () => {
    const { redoStack, nodes, edges, definition } = get()
    if (redoStack.length === 0) return
    const snapshot = redoStack.at(-1)
    if (!snapshot) return
    const current: WorkflowSnapshot = { nodes: structuredClone(nodes), edges: structuredClone(edges) }
    const restoredNodes = structuredClone(snapshot.nodes)
    const restoredEdges = structuredClone(snapshot.edges)
    const yaml = regenerateYaml(restoredNodes, restoredEdges, definition)
    set({
      nodes: restoredNodes,
      edges: restoredEdges,
      redoStack: redoStack.slice(0, -1),
      undoStack: [...get().undoStack, current],
      dirty: true,
      yamlPreview: yaml,
    })
  },
})
