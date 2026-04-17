import { useCallback, useEffect, useMemo, useState } from 'react'
import { createLogger } from '@/lib/logger'
import { ReactFlow, ReactFlowProvider, Background, MiniMap, type Node } from '@xyflow/react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { Workflow } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router'
import { useWorkflowsStore } from '@/stores/workflows'
import { ROUTES } from '@/router/routes'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { EmptyState } from '@/components/ui/empty-state'
import { useToastStore } from '@/stores/toast'
import { useWorkflowEditorStore } from '@/stores/workflow-editor'
import type { WorkflowNodeType } from '@/api/types'
import { StartNode } from './workflow-editor/StartNode'
import { EndNode } from './workflow-editor/EndNode'
import { TaskNode } from './workflow-editor/TaskNode'
import { AgentAssignmentNode } from './workflow-editor/AgentAssignmentNode'
import { ConditionalNode } from './workflow-editor/ConditionalNode'
import { ParallelSplitNode } from './workflow-editor/ParallelSplitNode'
import { ParallelJoinNode } from './workflow-editor/ParallelJoinNode'
import { SubworkflowNode } from './workflow-editor/SubworkflowNode'
import { SequentialEdge } from './workflow-editor/SequentialEdge'
import { ConditionalEdge } from './workflow-editor/ConditionalEdge'
import { WorkflowToolbar } from './workflow-editor/WorkflowToolbar'
import { VersionHistoryPanel } from './workflow-editor/VersionHistoryPanel'
import { VersionDiffViewer } from './workflow-editor/VersionDiffViewer'
import { WorkflowNodeDrawer } from './workflow-editor/WorkflowNodeDrawer'
import { WorkflowYamlPreview } from './workflow-editor/WorkflowYamlPreview'
import { WorkflowEditorSkeleton } from './workflow-editor/WorkflowEditorSkeleton'
import { WorkflowYamlEditor } from './workflow-editor/WorkflowYamlEditor'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'

const log = createLogger('WorkflowEditor')

// Declared outside component for stable reference identity
const nodeTypes = {
  start: StartNode,
  end: EndNode,
  task: TaskNode,
  agent_assignment: AgentAssignmentNode,
  conditional: ConditionalNode,
  parallel_split: ParallelSplitNode,
  parallel_join: ParallelJoinNode,
  subworkflow: SubworkflowNode,
}

const edgeTypes = {
  sequential: SequentialEdge,
  conditional: ConditionalEdge,
}

const VIEWPORT_KEY = 'synthorg:workflow:viewport'

function saveViewport(viewport: { x: number; y: number; zoom: number }) {
  try {
    localStorage.setItem(VIEWPORT_KEY, JSON.stringify(viewport))
  } catch (err) {
    log.warn('Failed to save viewport to localStorage:', err)
  }
}

function loadViewport(): { x: number; y: number; zoom: number } | undefined {
  try {
    const stored = localStorage.getItem(VIEWPORT_KEY)
    if (!stored) return undefined
    const parsed: unknown = JSON.parse(stored)
    const rec = parsed as Record<string, unknown>
    if (
      typeof parsed === 'object' && parsed !== null &&
      typeof rec.x === 'number' && Number.isFinite(rec.x) &&
      typeof rec.y === 'number' && Number.isFinite(rec.y) &&
      typeof rec.zoom === 'number' && Number.isFinite(rec.zoom) && (rec.zoom as number) > 0
    ) {
      return parsed as { x: number; y: number; zoom: number }
    }
  } catch (err) {
    log.warn('Failed to load viewport from localStorage:', err)
  }
  return undefined
}

function WorkflowEditorInner() {
  // Individual selectors to avoid unnecessary re-renders
  const nodes = useWorkflowEditorStore((s) => s.nodes)
  const edges = useWorkflowEditorStore((s) => s.edges)
  const definition = useWorkflowEditorStore((s) => s.definition)
  const selectedNodeId = useWorkflowEditorStore((s) => s.selectedNodeId)
  const dirty = useWorkflowEditorStore((s) => s.dirty)
  const saving = useWorkflowEditorStore((s) => s.saving)
  const loading = useWorkflowEditorStore((s) => s.loading)
  const error = useWorkflowEditorStore((s) => s.error)
  const validationResult = useWorkflowEditorStore((s) => s.validationResult)
  const validating = useWorkflowEditorStore((s) => s.validating)
  const undoStack = useWorkflowEditorStore((s) => s.undoStack)
  const redoStack = useWorkflowEditorStore((s) => s.redoStack)
  const yamlPreview = useWorkflowEditorStore((s) => s.yamlPreview)
  const loadDefinition = useWorkflowEditorStore((s) => s.loadDefinition)
  const createDefinition = useWorkflowEditorStore((s) => s.createDefinition)
  const saveDefinition = useWorkflowEditorStore((s) => s.saveDefinition)
  const addNode = useWorkflowEditorStore((s) => s.addNode)
  const updateNodeConfig = useWorkflowEditorStore((s) => s.updateNodeConfig)
  const onConnect = useWorkflowEditorStore((s) => s.onConnect)
  const onNodesChange = useWorkflowEditorStore((s) => s.onNodesChange)
  const onEdgesChange = useWorkflowEditorStore((s) => s.onEdgesChange)
  const selectNode = useWorkflowEditorStore((s) => s.selectNode)
  const undo = useWorkflowEditorStore((s) => s.undo)
  const redo = useWorkflowEditorStore((s) => s.redo)
  const validate = useWorkflowEditorStore((s) => s.validate)
  const exportYaml = useWorkflowEditorStore((s) => s.exportYaml)
  const versionHistoryOpen = useWorkflowEditorStore((s) => s.versionHistoryOpen)
  const toggleVersionHistory = useWorkflowEditorStore((s) => s.toggleVersionHistory)

  const [editorMode, setEditorMode] = useState<'visual' | 'yaml'>('visual')

  const addToast = useToastStore((s) => s.add)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const defId = searchParams.get('id')

  const defaultViewport = useMemo(() => loadViewport(), [])

  useEffect(() => {
    if (defId) {
      loadDefinition(defId)
    } else {
      createDefinition('New Workflow', 'sequential_pipeline')
    }
  }, [defId, loadDefinition, createDefinition])

  // Copy/paste keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
        // Only handle in visual mode, not in inputs/textareas/contenteditable
        const el = e.target as HTMLElement
        const tag = el.tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
        if (el.isContentEditable || el.closest('[contenteditable="true"]')) return
        if (editorMode !== 'visual') return
        e.preventDefault()
        useWorkflowEditorStore.getState().copySelectedNodes()
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
        const el = e.target as HTMLElement
        const tag = el.tagName
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
        if (el.isContentEditable || el.closest('[contenteditable="true"]')) return
        if (editorMode !== 'visual') return
        e.preventDefault()
        useWorkflowEditorStore.getState().pasteNodes()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [editorMode])

  const handleAddNode = useCallback(
    (type: WorkflowNodeType) => {
      addNode(type, { x: 250 + Math.random() * 100, y: 150 + Math.random() * 200 })
    },
    [addNode],
  )

  const handleNodeClick = useCallback(
    (_event: ReactMouseEvent, node: Node) => {
      selectNode(node.id)
    },
    [selectNode],
  )

  const handlePaneClick = useCallback(() => {
    selectNode(null)
  }, [selectNode])

  const handleExport = useCallback(async () => {
    try {
      const yamlStr = await exportYaml()
      const blob = new Blob([yamlStr], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${useWorkflowEditorStore.getState().definition?.name ?? 'workflow'}.yaml`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      addToast({ variant: 'success', title: 'YAML exported' })
    } catch (err) {
      log.error('YAML export failed', sanitizeForLog(err))
      addToast({ variant: 'error', title: 'Export failed', description: getErrorMessage(err) })
    }
  }, [exportYaml, addToast])

  const handleSave = useCallback(async () => {
    await saveDefinition()
    const storeError = useWorkflowEditorStore.getState().error
    if (!storeError) {
      addToast({ variant: 'success', title: 'Workflow saved' })
    }
  }, [saveDefinition, addToast])

  const handleValidate = useCallback(async () => {
    await validate()
    const result = useWorkflowEditorStore.getState().validationResult
    if (result) {
      addToast({
        variant: result.valid ? 'success' : 'warning',
        title: result.valid ? 'Workflow is valid' : `${result.errors.length} validation error(s)`,
      })
    }
  }, [validate, addToast])

  const handleDrawerClose = useCallback(() => selectNode(null), [selectNode])

  const selectedNode = selectedNodeId
    ? nodes.find((n) => n.id === selectedNodeId) ?? null
    : null

  const handleConfigChange = useCallback(
    (config: Record<string, unknown>) => {
      if (selectedNodeId) updateNodeConfig(selectedNodeId, config)
    },
    [selectedNodeId, updateNodeConfig],
  )

  const handleSwitchWorkflow = useCallback(
    (id: string) => {
      navigate(`${ROUTES.WORKFLOW_EDITOR}?id=${encodeURIComponent(id)}`)
    },
    [navigate],
  )

  const handleSaveAsNew = useCallback(async () => {
    const state = useWorkflowEditorStore.getState()
    if (!state.definition) return
    // Use current editor nodes/edges, not the last persisted definition
    const nodeData = state.nodes.map((n) => ({
      id: n.id,
      type: (n.data as Record<string, unknown>)?.nodeType as string ?? n.type ?? 'task',
      label: (n.data as Record<string, unknown>)?.label as string ?? n.id,
      position_x: n.position.x,
      position_y: n.position.y,
      config: (n.data as Record<string, unknown>)?.config as Record<string, unknown> ?? {},
    }))
    const edgeData = state.edges.map((e) => ({
      id: e.id,
      source_node_id: e.source,
      target_node_id: e.target,
      type: ((e.data as Record<string, unknown>)?.edgeType as string) ?? 'sequential',
      label: ((e.data as Record<string, unknown>)?.label as string) ?? null,
    }))
    const created = await useWorkflowsStore.getState().createWorkflow({
      name: `${state.definition.name} (Copy)`,
      description: state.definition.description || undefined,
      workflow_type: state.definition.workflow_type,
      nodes: nodeData,
      edges: edgeData,
    })
    if (!created) return
    navigate(`${ROUTES.WORKFLOW_EDITOR}?id=${encodeURIComponent(created.id)}`)
  }, [navigate])

  const handleMoveEnd = useCallback((_event: unknown, viewport: { x: number; y: number; zoom: number }) => {
    saveViewport(viewport)
  }, [])

  if (loading) return <WorkflowEditorSkeleton />

  if (!loading && !definition && error) {
    return (
      <EmptyState
        icon={Workflow}
        title="Failed to load workflow"
        description={error}
      />
    )
  }

  return (
    <div className="flex h-full flex-col">
      {error && (
        <div role="alert" className="mb-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger">
          {error}
        </div>
      )}

      <div className="mb-2">
        <WorkflowToolbar
          onAddNode={handleAddNode}
          onUndo={undo}
          onRedo={redo}
          onSave={handleSave}
          onValidate={handleValidate}
          onExport={handleExport}
          onHistory={toggleVersionHistory}
          onSaveAsNew={handleSaveAsNew}
          onSwitchWorkflow={handleSwitchWorkflow}
          currentWorkflowId={defId}
          editorMode={editorMode}
          onEditorModeChange={setEditorMode}
          canUndo={undoStack.length > 0}
          canRedo={redoStack.length > 0}
          dirty={dirty}
          saving={saving}
          validating={validating}
          validationValid={validationResult ? validationResult.valid : null}
        />
      </div>

      {editorMode === 'visual' ? (
        <>
          <div className="relative min-h-0 flex-1 rounded-lg border border-border">
            {/*
             * Accessible text summary of the graph. ReactFlow's visual
             * canvas is mouse-first; screen-reader users get a
             * sr-only outline of nodes and edges here, referenced via
             * `aria-describedby` on the canvas. The YAML editor below
             * the canvas is the full-fidelity keyboard-accessible
             * alternative for editing.
             */}
            <section
              id="workflow-editor-node-summary"
              aria-labelledby="workflow-editor-node-summary-heading"
              className="sr-only"
            >
              <h2 id="workflow-editor-node-summary-heading">
                Workflow graph summary
              </h2>
              <h3 id="workflow-editor-node-summary-nodes">
                Nodes ({nodes.length})
              </h3>
              <ul aria-labelledby="workflow-editor-node-summary-nodes">
                {nodes.map((node) => {
                  const label =
                    (node.data && typeof node.data === 'object' && 'label' in node.data
                      ? String((node.data as { label?: unknown }).label ?? '')
                      : '') ||
                    node.type ||
                    node.id
                  return (
                    <li key={node.id}>
                      {`Node ${node.id} (${node.type ?? 'unknown'}): ${label}`}
                    </li>
                  )
                })}
              </ul>
              <h3 id="workflow-editor-node-summary-edges">
                Edges ({edges.length})
              </h3>
              <ul aria-labelledby="workflow-editor-node-summary-edges">
                {edges.map((edge) => {
                  // Always expose topology (source → target); append
                  // the human label in parens when it is set, so the
                  // screen-reader summary retains both the graph shape
                  // and any branch semantics. Labels may live on
                  // ``edge.label`` (xyflow default) or on
                  // ``edge.data.label`` when the persistence layer
                  // stores branch metadata under ``data``.
                  const topology = `${edge.source} → ${edge.target}`
                  const dataLabel =
                    edge.data && typeof edge.data === 'object' &&
                      'label' in edge.data &&
                      typeof (edge.data as { label?: unknown }).label === 'string'
                      ? ((edge.data as { label: string }).label)
                      : ''
                  const rawLabel =
                    (typeof edge.label === 'string' && edge.label) || dataLabel
                  const text = rawLabel ? `${topology} (${rawLabel})` : topology
                  return <li key={edge.id}>{`Edge: ${text}`}</li>
                })}
              </ul>
            </section>
            <ReactFlow
              aria-label="Workflow editor canvas"
              aria-describedby="workflow-editor-node-summary"
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              defaultViewport={defaultViewport}
              fitView={!defaultViewport}
              fitViewOptions={{ padding: 0.2 }}
              onMoveEnd={handleMoveEnd}
              onNodeClick={handleNodeClick}
              onPaneClick={handlePaneClick}
              onConnect={onConnect}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              selectionOnDrag
              minZoom={0.1}
              maxZoom={2}
              proOptions={{ hideAttribution: true }}
            >
              <Background color="var(--color-border)" gap={24} size={1} />
              <MiniMap
                position="bottom-right"
                pannable
                zoomable
                style={{ backgroundColor: 'var(--so-bg-surface)' }}
                maskColor="var(--so-bg-overlay)"
                nodeColor={(node) => {
                  switch (node.type) {
                    case 'start':
                    case 'end':
                      return 'var(--so-accent)'
                    case 'task':
                      return 'var(--so-accent)'
                    case 'conditional':
                      return 'var(--so-warning)'
                    case 'parallel_split':
                    case 'parallel_join':
                      return 'var(--so-success)'
                    case 'agent_assignment':
                      return 'var(--so-accent-dim)'
                    default:
                      return 'var(--so-text-muted)'
                  }
                }}
              />
            </ReactFlow>
          </div>

          <WorkflowYamlPreview yaml={yamlPreview} />
        </>
      ) : (
        <div className="min-h-0 flex-1 rounded-lg border border-border">
          <WorkflowYamlEditor initialYaml={yamlPreview} />
        </div>
      )}

      {editorMode === 'visual' && (
        <WorkflowNodeDrawer
          open={selectedNode !== null && !versionHistoryOpen}
          onClose={handleDrawerClose}
          nodeId={selectedNodeId}
          nodeType={(selectedNode?.type as WorkflowNodeType) ?? null}
          nodeLabel={String((selectedNode?.data as Record<string, unknown>)?.label ?? 'Node')}
          config={((selectedNode?.data as Record<string, unknown>)?.config as Record<string, unknown>) ?? {}}
          onConfigChange={handleConfigChange}
        />
      )}

      <VersionHistoryPanel
        open={versionHistoryOpen}
        onClose={toggleVersionHistory}
      />

      <VersionDiffViewer />
    </div>
  )
}

export default function WorkflowEditorPage() {
  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-section-gap">
      <h1 className="text-lg font-semibold text-foreground">Workflow Editor</h1>

      <ErrorBoundary level="section">
        <ReactFlowProvider>
          <WorkflowEditorInner />
        </ReactFlowProvider>
      </ErrorBoundary>
    </div>
  )
}
