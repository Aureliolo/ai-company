import type { MouseEvent as ReactMouseEvent } from 'react'
import {
  Background,
  MiniMap,
  ReactFlow,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type Connection,
  type EdgeTypes,
  type NodeTypes,
} from '@xyflow/react'

interface WorkflowEditorCanvasProps {
  nodes: readonly Node[]
  edges: readonly Edge[]
  nodeTypes: NodeTypes
  edgeTypes: EdgeTypes
  defaultViewport: { x: number; y: number; zoom: number } | undefined
  onNodeClick: (event: ReactMouseEvent, node: Node) => void
  onPaneClick: () => void
  onConnect: (connection: Connection) => void
  onNodesChange: (changes: NodeChange[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onMoveEnd: (event: unknown, viewport: { x: number; y: number; zoom: number }) => void
}

function miniMapNodeColor(node: Node): string {
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
}

export function WorkflowEditorCanvas(props: WorkflowEditorCanvasProps) {
  const {
    nodes,
    edges,
    nodeTypes,
    edgeTypes,
    defaultViewport,
    onNodeClick,
    onPaneClick,
    onConnect,
    onNodesChange,
    onEdgesChange,
    onMoveEnd,
  } = props

  return (
    <div className="relative min-h-0 flex-1 rounded-lg border border-border">
      {/*
        Accessible text summary of the graph. ReactFlow's visual canvas
        is mouse-first; screen-reader users get a sr-only outline of nodes
        and edges here, referenced via aria-describedby on the canvas.
      */}
      <section
        id="workflow-editor-node-summary"
        aria-labelledby="workflow-editor-node-summary-heading"
        className="sr-only"
      >
        <h2 id="workflow-editor-node-summary-heading">Workflow graph summary</h2>
        <h3 id="workflow-editor-node-summary-nodes">Nodes ({nodes.length})</h3>
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
        <h3 id="workflow-editor-node-summary-edges">Edges ({edges.length})</h3>
        <ul aria-labelledby="workflow-editor-node-summary-edges">
          {edges.map((edge) => {
            const topology = `${edge.source} → ${edge.target}`
            const dataLabel =
              edge.data && typeof edge.data === 'object' &&
                'label' in edge.data &&
                typeof (edge.data as { label?: unknown }).label === 'string'
                ? (edge.data as { label: string }).label
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
        nodes={nodes as Node[]}
        edges={edges as Edge[]}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultViewport={defaultViewport}
        fitView={!defaultViewport}
        fitViewOptions={{ padding: 0.2 }}
        onMoveEnd={onMoveEnd}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
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
          nodeColor={miniMapNodeColor}
        />
      </ReactFlow>
    </div>
  )
}
