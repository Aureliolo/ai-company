import { useCallback, useEffect, useMemo } from 'react'
import { ReactFlow, ReactFlowProvider, Background, type Node } from '@xyflow/react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { Workflow } from 'lucide-react'
import { useSearchParams } from 'react-router'
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
import { SequentialEdge } from './workflow-editor/SequentialEdge'
import { ConditionalEdge } from './workflow-editor/ConditionalEdge'
import { WorkflowToolbar } from './workflow-editor/WorkflowToolbar'
import { WorkflowNodeDrawer } from './workflow-editor/WorkflowNodeDrawer'
import { WorkflowYamlPreview } from './workflow-editor/WorkflowYamlPreview'
import { WorkflowEditorSkeleton } from './workflow-editor/WorkflowEditorSkeleton'

// Declared outside component for stable reference identity
const nodeTypes = {
  start: StartNode,
  end: EndNode,
  task: TaskNode,
  agent_assignment: AgentAssignmentNode,
  conditional: ConditionalNode,
  parallel_split: ParallelSplitNode,
  parallel_join: ParallelJoinNode,
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
    console.warn('Failed to save viewport to localStorage:', err)
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
    console.warn('Failed to load viewport from localStorage:', err)
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

  const addToast = useToastStore((s) => s.add)
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
      const message = err instanceof Error ? err.message : 'Export failed'
      addToast({ variant: 'error', title: 'Export failed', description: message })
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
          canUndo={undoStack.length > 0}
          canRedo={redoStack.length > 0}
          dirty={dirty}
          saving={saving}
          validating={validating}
          validationValid={validationResult ? validationResult.valid : null}
        />
      </div>

      <div className="relative min-h-0 flex-1 rounded-lg border border-border">
        <ReactFlow
          aria-label="Workflow editor canvas"
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
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--color-border)" gap={24} size={1} />
        </ReactFlow>

        {/* ARIA live region for editor actions */}
{/* Toast system handles ARIA announcements -- removed empty live region */}
      </div>

      <WorkflowYamlPreview yaml={yamlPreview} />

      <WorkflowNodeDrawer
        open={selectedNode !== null}
        onClose={handleDrawerClose}
        nodeId={selectedNodeId}
        nodeType={(selectedNode?.type as WorkflowNodeType) ?? null}
        nodeLabel={String((selectedNode?.data as Record<string, unknown>)?.label ?? 'Node')}
        config={((selectedNode?.data as Record<string, unknown>)?.config as Record<string, unknown>) ?? {}}
        onConfigChange={handleConfigChange}
      />
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
