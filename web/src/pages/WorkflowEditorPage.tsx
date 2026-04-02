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
  } catch {
    // Ignore storage errors
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
  } catch {
    // Ignore parse errors
  }
  return undefined
}

function WorkflowEditorInner() {
  const {
    nodes,
    edges,
    definition,
    selectedNodeId,
    dirty,
    saving,
    loading,
    error,
    validationResult,
    validating,
    undoStack,
    redoStack,
    yamlPreview,
    loadDefinition,
    createDefinition,
    saveDefinition,
    addNode,
    updateNodeConfig,
    onConnect,
    onNodesChange,
    onEdgesChange,
    selectNode,
    undo,
    redo,
    validate,
    exportYaml,
  } = useWorkflowEditorStore()

  const addToast = useToastStore((s) => s.add)
  const [searchParams] = useSearchParams()
  const defId = searchParams.get('id')

  const defaultViewport = useMemo(() => loadViewport(), [])

  // Load or create on mount
  useEffect(() => {
    if (defId) {
      loadDefinition(defId)
    } else {
      createDefinition('New Workflow', 'sequential_pipeline')
    }
  }, [defId, loadDefinition, createDefinition])

  const handleAddNode = useCallback(
    (type: WorkflowNodeType) => {
      // Place in the center area
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
      // Trigger file download
      const blob = new Blob([yamlStr], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${definition?.name ?? 'workflow'}.yaml`
      a.click()
      URL.revokeObjectURL(url)
      addToast({ variant: 'success', title: 'YAML exported' })
    } catch {
      addToast({ variant: 'error', title: 'Export failed' })
    }
  }, [exportYaml, definition, addToast])

  const handleSave = useCallback(async () => {
    await saveDefinition()
    addToast({ variant: 'success', title: 'Workflow saved' })
  }, [saveDefinition, addToast])

  const handleValidate = useCallback(async () => {
    await validate()
  }, [validate])

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

      <div className="relative flex-1 rounded-lg border border-border">
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
        <div className="sr-only" aria-live="assertive" />
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
    <div className="flex h-full flex-col gap-section-gap">
      <h1 className="text-lg font-semibold text-foreground">Workflow Editor</h1>

      <ErrorBoundary level="section">
        <ReactFlowProvider>
          <WorkflowEditorInner />
        </ReactFlowProvider>
      </ErrorBoundary>
    </div>
  )
}
