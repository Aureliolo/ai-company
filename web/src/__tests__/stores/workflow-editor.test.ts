import { beforeEach, describe, expect, it } from 'vitest'
import { useWorkflowEditorStore } from '@/stores/workflow-editor'

function resetStore() {
  useWorkflowEditorStore.setState({
    nodes: [],
    edges: [],
    selectedNodeId: null,
    dirty: false,
    yamlPreview: '',
    undoStack: [],
    redoStack: [],
    validationResult: null,
    validating: false,
    clipboard: null,
    definition: null,
    saving: false,
    loading: false,
    error: null,
    versionHistoryOpen: false,
    versions: [],
    versionsLoading: false,
    versionsHasMore: false,
    diffResult: null,
    diffLoading: false,
    _versionsRequestId: 0,
    _diffRequestId: 0,
  })
}

describe('workflow-editor composed store', () => {
  beforeEach(() => {
    resetStore()
  })

  describe('composition', () => {
    it('exposes graph slice actions', () => {
      const state = useWorkflowEditorStore.getState()
      expect(typeof state.addNode).toBe('function')
      expect(typeof state.removeNode).toBe('function')
      expect(typeof state.onConnect).toBe('function')
      expect(typeof state.selectNode).toBe('function')
    })

    it('exposes undo/redo slice actions', () => {
      const state = useWorkflowEditorStore.getState()
      expect(typeof state.undo).toBe('function')
      expect(typeof state.redo).toBe('function')
    })

    it('exposes validation, clipboard, persistence, versions slices', () => {
      const state = useWorkflowEditorStore.getState()
      expect(typeof state.validate).toBe('function')
      expect(typeof state.copySelectedNodes).toBe('function')
      expect(typeof state.pasteNodes).toBe('function')
      expect(typeof state.loadDefinition).toBe('function')
      expect(typeof state.saveDefinition).toBe('function')
      expect(typeof state.toggleVersionHistory).toBe('function')
      expect(typeof state.rollback).toBe('function')
    })

    it('initializes with empty graph and clean flags', () => {
      const state = useWorkflowEditorStore.getState()
      expect(state.nodes).toEqual([])
      expect(state.edges).toEqual([])
      expect(state.selectedNodeId).toBeNull()
      expect(state.dirty).toBe(false)
      expect(state.undoStack).toEqual([])
      expect(state.redoStack).toEqual([])
      expect(state.validationResult).toBeNull()
      expect(state.clipboard).toBeNull()
      expect(state.definition).toBeNull()
    })
  })

  describe('graph + undo-redo integration', () => {
    it('adds a node, marks dirty, and records an undo snapshot', () => {
      useWorkflowEditorStore.getState().addNode('task', { x: 10, y: 20 })

      const state = useWorkflowEditorStore.getState()
      expect(state.nodes).toHaveLength(1)
      expect(state.nodes[0]?.type).toBe('task')
      expect(state.nodes[0]?.position).toEqual({ x: 10, y: 20 })
      expect(state.dirty).toBe(true)
      expect(state.undoStack).toHaveLength(1)
      expect(state.redoStack).toEqual([])
    })

    it('undo restores prior state and pushes onto redo stack', () => {
      const store = useWorkflowEditorStore.getState()
      store.addNode('task', { x: 0, y: 0 })
      store.addNode('agent_assignment', { x: 100, y: 0 })

      expect(useWorkflowEditorStore.getState().nodes).toHaveLength(2)

      useWorkflowEditorStore.getState().undo()

      const state = useWorkflowEditorStore.getState()
      expect(state.nodes).toHaveLength(1)
      expect(state.redoStack).toHaveLength(1)
      expect(state.undoStack).toHaveLength(1)
    })

    it('redo re-applies the undone action', () => {
      const store = useWorkflowEditorStore.getState()
      store.addNode('task', { x: 0, y: 0 })
      store.addNode('agent_assignment', { x: 100, y: 0 })
      useWorkflowEditorStore.getState().undo()
      expect(useWorkflowEditorStore.getState().nodes).toHaveLength(1)

      useWorkflowEditorStore.getState().redo()

      const state = useWorkflowEditorStore.getState()
      expect(state.nodes).toHaveLength(2)
      expect(state.redoStack).toEqual([])
    })

    it('removeNode clears selectedNodeId when the removed node was selected', () => {
      const store = useWorkflowEditorStore.getState()
      store.addNode('task', { x: 0, y: 0 })
      const nodeId = useWorkflowEditorStore.getState().nodes[0]!.id
      store.selectNode(nodeId)
      expect(useWorkflowEditorStore.getState().selectedNodeId).toBe(nodeId)

      useWorkflowEditorStore.getState().removeNode(nodeId)

      const state = useWorkflowEditorStore.getState()
      expect(state.nodes).toHaveLength(0)
      expect(state.selectedNodeId).toBeNull()
    })
  })

  describe('versions slice', () => {
    it('toggleVersionHistory flips the open flag', () => {
      expect(useWorkflowEditorStore.getState().versionHistoryOpen).toBe(false)

      useWorkflowEditorStore.getState().toggleVersionHistory()
      expect(useWorkflowEditorStore.getState().versionHistoryOpen).toBe(true)

      useWorkflowEditorStore.getState().toggleVersionHistory()
      expect(useWorkflowEditorStore.getState().versionHistoryOpen).toBe(false)
    })

    it('clearDiff resets diffResult without other state', () => {
      useWorkflowEditorStore.setState({
        diffResult: {
          from_version: 1,
          to_version: 2,
          changes: [],
        } as never,
        diffLoading: false,
      })

      useWorkflowEditorStore.getState().clearDiff()

      expect(useWorkflowEditorStore.getState().diffResult).toBeNull()
    })
  })

  describe('persistence slice reset', () => {
    it('reset returns the store to its initial empty state', () => {
      const store = useWorkflowEditorStore.getState()
      store.addNode('task', { x: 5, y: 5 })
      expect(useWorkflowEditorStore.getState().nodes).toHaveLength(1)
      expect(useWorkflowEditorStore.getState().dirty).toBe(true)

      useWorkflowEditorStore.getState().reset()

      const state = useWorkflowEditorStore.getState()
      expect(state.nodes).toEqual([])
      expect(state.edges).toEqual([])
      expect(state.definition).toBeNull()
      expect(state.dirty).toBe(false)
      expect(state.undoStack).toEqual([])
      expect(state.redoStack).toEqual([])
    })
  })
})
