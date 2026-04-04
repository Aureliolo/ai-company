/**
 * Zustand store for the visual workflow editor.
 *
 * Manages nodes, edges, selection, undo/redo, validation,
 * YAML preview, and persistence via the API.
 */

import { create } from 'zustand'
import type { Node, Edge, Connection, NodeChange, EdgeChange } from '@xyflow/react'
import { applyNodeChanges, applyEdgeChanges } from '@xyflow/react'
import { createLogger } from '@/lib/logger'
import type {
  WorkflowDefinition,
  WorkflowDefinitionVersionSummary,
  WorkflowDiff,
  WorkflowValidationResult,
  WorkflowNodeType,
} from '@/api/types'

import {
  getWorkflow,
  createWorkflow,
  updateWorkflow,
  validateWorkflowDraft,
  listWorkflowVersions,
  getWorkflowDiff,
  rollbackWorkflow,
} from '@/api/endpoints/workflows'
import { generateYamlPreview } from '@/pages/workflow-editor/workflow-to-yaml'
import { copyNodes, pasteFromClipboard, type ClipboardData } from '@/pages/workflow-editor/copy-paste'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'

const log = createLogger('workflow-editor')
const MAX_UNDO = 50

interface WorkflowSnapshot {
  nodes: Node[]
  edges: Edge[]
}

export interface WorkflowEditorState {
  // Data
  definition: WorkflowDefinition | null
  nodes: Node[]
  edges: Edge[]

  // Selection & UI
  selectedNodeId: string | null
  dirty: boolean
  saving: boolean
  loading: boolean
  error: string | null

  // Validation
  validationResult: WorkflowValidationResult | null
  validating: boolean

  // Undo/redo
  undoStack: WorkflowSnapshot[]
  redoStack: WorkflowSnapshot[]

  // YAML preview
  yamlPreview: string

  // Clipboard
  clipboard: ClipboardData | null

  // Version history
  versionHistoryOpen: boolean
  versions: readonly WorkflowDefinitionVersionSummary[]
  versionsLoading: boolean
  versionsHasMore: boolean
  diffResult: WorkflowDiff | null
  diffLoading: boolean
  /** @internal Request counter to discard stale version responses. */
  _versionsRequestId: number
  /** @internal Request counter to discard stale diff responses. */
  _diffRequestId: number

  // Actions
  loadDefinition: (id: string) => Promise<void>
  createDefinition: (name: string, workflowType: string) => Promise<void>
  saveDefinition: () => Promise<void>
  addNode: (type: WorkflowNodeType, position: { x: number; y: number }) => void
  updateNodeConfig: (nodeId: string, config: Record<string, unknown>) => void
  removeNode: (nodeId: string) => void
  onConnect: (connection: Connection) => void
  removeEdge: (edgeId: string) => void
  onNodesChange: (changes: NodeChange[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  selectNode: (nodeId: string | null) => void
  undo: () => void
  redo: () => void
  validate: () => Promise<void>
  exportYaml: () => Promise<string>
  copySelectedNodes: () => void
  pasteNodes: () => void
  toggleVersionHistory: () => void
  loadVersions: () => Promise<void>
  loadMoreVersions: () => Promise<void>
  loadDiff: (fromVersion: number, toVersion: number) => Promise<void>
  clearDiff: () => void
  rollback: (targetVersion: number) => Promise<void>
  reset: () => void
}

function generateNodeId(): string {
  return `node-${crypto.randomUUID().slice(0, 8)}`
}

function generateEdgeId(): string {
  return `edge-${crypto.randomUUID().slice(0, 8)}`
}

function nodeTypeToEdgeType(
  sourceType: string | undefined,
): string {
  if (sourceType === 'conditional') {
    return 'conditional'
  }
  if (sourceType === 'parallel_split') return 'parallel_branch'
  return 'sequential'
}

function regenerateYaml(nodes: Node[], edges: Edge[], definition: WorkflowDefinition | null): string {
  return generateYamlPreview(
    nodes,
    edges,
    definition?.name ?? 'Untitled',
    definition?.workflow_type ?? 'sequential_pipeline',
  )
}

interface EdgeMeta {
  visualType: string
  sourceHandle: string | undefined
  edgeType: string
  branch: string | undefined
}

function mapPersistedEdge(edgeType: string): EdgeMeta {
  const isTrue = edgeType === 'conditional_true'
  const isFalse = edgeType === 'conditional_false'
  if (isTrue || isFalse) {
    return {
      visualType: 'conditional',
      sourceHandle: isTrue ? 'true' : 'false',
      edgeType,
      branch: isTrue ? 'true' : 'false',
    }
  }
  if (edgeType === 'parallel_branch') {
    return { visualType: 'parallel_branch', sourceHandle: undefined, edgeType, branch: undefined }
  }
  return { visualType: 'sequential', sourceHandle: undefined, edgeType, branch: undefined }
}

/** Parse a WorkflowDefinition into React Flow nodes, edges, and YAML. */
function parseDefinition(def: WorkflowDefinition): {
  nodes: Node[]
  edges: Edge[]
  yaml: string
} {
  const nodes: Node[] = def.nodes.map((n) => ({
    id: n.id,
    type: n.type,
    position: { x: n.position_x, y: n.position_y },
    data: { label: n.label, config: n.config },
  }))
  const edges: Edge[] = def.edges.map((e) => {
    const meta = mapPersistedEdge(e.type)
    return {
      id: e.id,
      source: e.source_node_id,
      target: e.target_node_id,
      type: meta.visualType,
      sourceHandle: meta.sourceHandle,
      data: { edgeType: meta.edgeType, branch: meta.branch },
      label: e.label ?? undefined,
    }
  })
  const yaml = regenerateYaml(nodes, edges, def)
  return { nodes, edges, yaml }
}

export const useWorkflowEditorStore = create<WorkflowEditorState>()((set, get) => ({
  definition: null,
  nodes: [],
  edges: [],
  selectedNodeId: null,
  dirty: false,
  saving: false,
  loading: false,
  error: null,
  validationResult: null,
  validating: false,
  undoStack: [],
  redoStack: [],
  yamlPreview: '',
  clipboard: null,

  versionHistoryOpen: false,
  versions: [],
  versionsLoading: false,
  versionsHasMore: false,
  diffResult: null,
  diffLoading: false,
  _versionsRequestId: 0,
  _diffRequestId: 0,

  loadDefinition: async (id: string) => {
    // Invalidate version/diff state and bump tokens when switching definitions.
    set((prev) => ({
      ...prev,
      loading: true,
      error: null,
      versions: [],
      versionsLoading: false,
      versionsHasMore: false,
      diffResult: null,
      diffLoading: false,
      _versionsRequestId: prev._versionsRequestId + 1,
      _diffRequestId: prev._diffRequestId + 1,
    }))
    try {
      const def = await getWorkflow(id)
      const { nodes, edges, yaml } = parseDefinition(def)
      set({
        definition: def,
        nodes,
        edges,
        loading: false,
        dirty: false,
        selectedNodeId: null,
        undoStack: [],
        redoStack: [],
        yamlPreview: yaml,
        validationResult: null,
      })
    } catch (err) {
      log.warn('Failed to load workflow definition', sanitizeForLog(err))
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  createDefinition: async (name: string, workflowType: string) => {
    set((prev) => ({
      ...prev,
      loading: true,
      error: null,
      versions: [],
      versionsLoading: false,
      versionsHasMore: false,
      diffResult: null,
      diffLoading: false,
      _versionsRequestId: prev._versionsRequestId + 1,
      _diffRequestId: prev._diffRequestId + 1,
    }))
    try {
      const startId = generateNodeId()
      const endId = generateNodeId()
      const def = await createWorkflow({
        name,
        workflow_type: workflowType,
        nodes: [
          { id: startId, type: 'start', label: 'Start', position_x: 250, position_y: 50, config: {} },
          { id: endId, type: 'end', label: 'End', position_x: 250, position_y: 400, config: {} },
        ],
        edges: [],
      })
      const nodes: Node[] = [
        { id: startId, type: 'start', position: { x: 250, y: 50 }, data: { label: 'Start', config: {} } },
        { id: endId, type: 'end', position: { x: 250, y: 400 }, data: { label: 'End', config: {} } },
      ]
      const yaml = regenerateYaml(nodes, [], def)
      set({
        definition: def,
        nodes,
        edges: [],
        loading: false,
        dirty: false,
        selectedNodeId: null,
        undoStack: [],
        redoStack: [],
        yamlPreview: yaml,
        validationResult: null,
      })
    } catch (err) {
      log.warn('Failed to create workflow definition', sanitizeForLog(err))
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  saveDefinition: async () => {
    const { definition, nodes, edges } = get()
    if (!definition) {
      set({ error: 'Cannot save: no workflow loaded' })
      return
    }
    // Validate types before saving -- abort with error if any are missing
    const badNodes = nodes.filter((n) => !n.type)
    const badEdges = edges.filter((e) => !(e.data as Record<string, unknown>)?.edgeType)
    if (badNodes.length > 0 || badEdges.length > 0) {
      const parts: string[] = []
      if (badNodes.length > 0) parts.push(`nodes missing type: ${badNodes.map((n) => n.id).join(', ')}`)
      if (badEdges.length > 0) parts.push(`edges missing type: ${badEdges.map((e) => e.id).join(', ')}`)
      set({ error: `Cannot save -- ${parts.join('; ')}. Remove and re-add the affected items.` })
      return
    }

    set({ saving: true, error: null })
    try {
      const updatedDef = await updateWorkflow(definition.id, {
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type!,
          label: (n.data as Record<string, unknown>)?.label ?? n.id,
          position_x: n.position.x,
          position_y: n.position.y,
          config: ((n.data as Record<string, unknown>)?.config as Record<string, unknown>) ?? {},
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source_node_id: e.source,
          target_node_id: e.target,
          type: ((e.data as Record<string, unknown>)?.edgeType as string) ?? 'sequential',
          label: (e.label as string) ?? null,
        })),
        expected_version: definition.version,
      })
      set({ definition: updatedDef, saving: false, dirty: false, validationResult: null })
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 409 && definition) {
        log.warn('Version conflict saving workflow, reloading', sanitizeForLog(err))
        set({ saving: false, error: 'Version conflict -- another save occurred. Reloading...' })
        await get().loadDefinition(definition.id)
      } else {
        log.warn('Failed to save workflow definition', sanitizeForLog(err))
        set({ saving: false, error: getErrorMessage(err) })
      }
    }
  },

  addNode: (type: WorkflowNodeType, position: { x: number; y: number }) => {
    const { nodes, edges, definition } = get()
    const snapshot: WorkflowSnapshot = { nodes: structuredClone(nodes), edges: structuredClone(edges) }
    const id = generateNodeId()
    const label = type.charAt(0).toUpperCase() + type.slice(1).replaceAll('_', ' ')
    const newNode: Node = {
      id,
      type,
      position,
      data: { label, config: {} },
    }
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

  updateNodeConfig: (nodeId: string, config: Record<string, unknown>) => {
    const { nodes, edges, definition } = get()
    const snapshot: WorkflowSnapshot = { nodes: structuredClone(nodes), edges: structuredClone(edges) }
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

  removeNode: (nodeId: string) => {
    const { nodes, edges, definition } = get()
    const snapshot: WorkflowSnapshot = { nodes: structuredClone(nodes), edges: structuredClone(edges) }
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

  onConnect: (connection: Connection) => {
    const { nodes, edges, definition } = get()
    if (!connection.source || !connection.target) return
    const snapshot: WorkflowSnapshot = { nodes: structuredClone(nodes), edges: structuredClone(edges) }
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

  removeEdge: (edgeId: string) => {
    const { nodes, edges, definition } = get()
    const snapshot: WorkflowSnapshot = { nodes: structuredClone(nodes), edges: structuredClone(edges) }
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

  onNodesChange: (changes: NodeChange[]) => {
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

  onEdgesChange: (changes: EdgeChange[]) => {
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

  selectNode: (nodeId: string | null) => {
    set({ selectedNodeId: nodeId })
  },

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

  validate: async () => {
    const { definition, nodes, edges } = get()
    if (!definition) {
      set({ error: 'Cannot validate: no workflow loaded' })
      return
    }
    const badNodes = nodes.filter((n) => !n.type)
    const badEdges = edges.filter((e) => !(e.data as Record<string, unknown>)?.edgeType)
    if (badNodes.length > 0 || badEdges.length > 0) {
      const parts: string[] = []
      if (badNodes.length > 0) parts.push(`nodes missing type: ${badNodes.map((n) => n.id).join(', ')}`)
      if (badEdges.length > 0) parts.push(`edges missing type: ${badEdges.map((e) => e.id).join(', ')}`)
      set({ error: `Cannot validate -- ${parts.join('; ')}. Remove and re-add the affected items.`, validating: false })
      return
    }

    set({ validating: true })
    try {
      const result = await validateWorkflowDraft({
        name: definition.name,
        workflow_type: definition.workflow_type,
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type!,
          label: (n.data as Record<string, unknown>)?.label ?? n.id,
          position_x: n.position.x,
          position_y: n.position.y,
          config: ((n.data as Record<string, unknown>)?.config as Record<string, unknown>) ?? {},
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source_node_id: e.source,
          target_node_id: e.target,
          type: ((e.data as Record<string, unknown>)?.edgeType as string) ?? 'sequential',
          label: (e.label as string) ?? null,
        })),
      })
      set({ validationResult: result, validating: false })
    } catch (err) {
      log.warn('Workflow validation failed', sanitizeForLog(err))
      set({ validating: false, validationResult: null, error: getErrorMessage(err) })
    }
  },

  exportYaml: async () => {
    const { definition, yamlPreview } = get()
    if (!definition) throw new Error('Cannot export: no workflow loaded')
    return yamlPreview
  },

  copySelectedNodes: () => {
    const { nodes, edges } = get()
    const selectedIds = new Set(nodes.filter((n) => n.selected).map((n) => n.id))
    const clipboard = copyNodes(selectedIds, nodes, edges)
    if (clipboard) set({ clipboard })
  },

  pasteNodes: () => {
    const { clipboard, nodes, edges, definition } = get()
    if (!clipboard) return
    const pasted = pasteFromClipboard(clipboard)
    const newNodes = [...nodes.map((n) => ({ ...n, selected: false })), ...pasted.nodes]
    const newEdges = [...edges, ...pasted.edges]
    const yamlPreview = definition
      ? generateYamlPreview(newNodes, newEdges, definition.name, definition.workflow_type)
      : ''
    set({
      nodes: newNodes,
      edges: newEdges,
      dirty: true,
      yamlPreview,
      undoStack: [...get().undoStack.slice(-(MAX_UNDO - 1)), { nodes, edges }],
      redoStack: [],
    })
  },

  toggleVersionHistory: () => {
    const open = !get().versionHistoryOpen
    set({ versionHistoryOpen: open })
    if (open) {
      useWorkflowEditorStore.getState().loadVersions()
    }
  },

  loadVersions: async () => {
    const defn = get().definition
    if (!defn) return
    const reqId = get()._versionsRequestId + 1
    set({ versionsLoading: true, _versionsRequestId: reqId })
    try {
      const limit = 50
      const result = await listWorkflowVersions(defn.id, { limit })
      if (get()._versionsRequestId !== reqId) return
      set({
        versions: result.data,
        versionsLoading: false,
        versionsHasMore: result.data.length >= limit,
      })
    } catch (err) {
      if (get()._versionsRequestId !== reqId) return
      log.warn('Failed to load versions', sanitizeForLog(err))
      set({ versionsLoading: false, error: getErrorMessage(err) })
    }
  },

  loadMoreVersions: async () => {
    const { definition: defn, versionsLoading, versionsHasMore } = get()
    if (!defn || versionsLoading || !versionsHasMore) return
    const reqId = get()._versionsRequestId + 1
    const offset = get().versions.length
    set({ versionsLoading: true, _versionsRequestId: reqId })
    try {
      const limit = 50
      const result = await listWorkflowVersions(defn.id, { limit, offset })
      if (get()._versionsRequestId !== reqId) return
      set((prev) => ({
        ...prev,
        versions: [...prev.versions, ...result.data],
        versionsLoading: false,
        versionsHasMore: result.data.length >= limit,
      }))
    } catch (err) {
      if (get()._versionsRequestId !== reqId) return
      log.warn('Failed to load more versions', sanitizeForLog(err))
      set({ versionsLoading: false, error: getErrorMessage(err) })
    }
  },

  loadDiff: async (fromVersion: number, toVersion: number) => {
    const defn = get().definition
    if (!defn) return
    const reqId = get()._diffRequestId + 1
    set({ diffLoading: true, _diffRequestId: reqId })
    try {
      const diff = await getWorkflowDiff(defn.id, fromVersion, toVersion)
      if (get()._diffRequestId !== reqId) return
      set({ diffResult: diff, diffLoading: false })
    } catch (err) {
      if (get()._diffRequestId !== reqId) return
      log.warn('Failed to load diff', sanitizeForLog(err))
      set({ diffLoading: false, error: getErrorMessage(err) })
    }
  },

  clearDiff: () => {
    // Increment token to discard any in-flight diff response.
    set((prev) => ({
      ...prev,
      diffResult: null,
      diffLoading: false,
      _diffRequestId: prev._diffRequestId + 1,
    }))
  },

  rollback: async (targetVersion: number) => {
    const defn = get().definition
    if (!defn) return
    set({ saving: true, error: null })
    try {
      const updated = await rollbackWorkflow(defn.id, {
        target_version: targetVersion,
        expected_version: defn.version,
      })
      // Hydrate editor state immediately from the rollback response
      // so the UI reflects the rolled-back version even if the
      // subsequent reload fails.
      const { nodes, edges, yaml } = parseDefinition(updated)
      set((prev) => ({
        ...prev,
        definition: updated,
        nodes,
        edges,
        yamlPreview: yaml,
        saving: false,
        dirty: false,
        diffResult: null,
        _diffRequestId: prev._diffRequestId + 1,
        selectedNodeId: null,
        undoStack: [],
        redoStack: [],
        validationResult: null,
      }))
      await useWorkflowEditorStore.getState().loadVersions()
    } catch (err) {
      log.warn('Rollback failed', sanitizeForLog(err))
      set({ saving: false, error: getErrorMessage(err) })
    }
  },

  reset: () => {
    set({
      definition: null,
      nodes: [],
      edges: [],
      selectedNodeId: null,
      dirty: false,
      saving: false,
      loading: false,
      error: null,
      validationResult: null,
      validating: false,
      undoStack: [],
      redoStack: [],
      yamlPreview: '',
      clipboard: null,
      versionHistoryOpen: false,
      versions: [],
      versionsLoading: false,
      versionsHasMore: false,
      diffResult: null,
      diffLoading: false,
      _versionsRequestId: get()._versionsRequestId + 1,
      _diffRequestId: get()._diffRequestId + 1,
    })
  },
}))
