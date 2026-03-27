import { useMemo } from 'react'
import { ReactFlow, Background, Controls, type Node, type Edge, MarkerType, Position } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { getTaskStatusColor, getTaskStatusLabel } from '@/utils/tasks'
import type { Task } from '@/api/types'

export interface TaskDependencyGraphProps {
  tasks: Task[]
  onSelectTask: (taskId: string) => void
}

function buildGraph(tasks: Task[]): { nodes: Node[]; edges: Edge[] } {
  const taskMap = new Map(tasks.map((t) => [t.id, t]))
  const nodes: Node[] = []
  const edges: Edge[] = []
  const COL_WIDTH = 280
  const ROW_HEIGHT = 80

  // Only include tasks that have dependencies or are depended upon
  const relevantIds = new Set<string>()
  for (const task of tasks) {
    if (task.dependencies.length > 0) {
      relevantIds.add(task.id)
      for (const depId of task.dependencies) {
        relevantIds.add(depId)
      }
    }
  }

  const relevantTasks = tasks.filter((t) => relevantIds.has(t.id))
  if (relevantTasks.length === 0) return { nodes: [], edges: [] }

  // Arrange in a simple grid
  relevantTasks.forEach((task, i) => {
    const col = i % 4
    const row = Math.floor(i / 4)
    const color = getTaskStatusColor(task.status)
    const cssColor = color === 'text-secondary' ? 'var(--so-text-secondary)' : `var(--so-${color})`

    nodes.push({
      id: task.id,
      position: { x: col * COL_WIDTH, y: row * ROW_HEIGHT },
      data: { label: task.title },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      style: {
        borderColor: cssColor,
        borderWidth: 2,
        borderRadius: 8,
        padding: '8px 12px',
        fontSize: 12,
        maxWidth: 240,
        background: 'var(--so-card)',
        color: 'var(--so-foreground)',
      },
    })
  })

  // Build edges from dependencies
  for (const task of relevantTasks) {
    for (const depId of task.dependencies) {
      if (taskMap.has(depId)) {
        edges.push({
          id: `${depId}->${task.id}`,
          source: depId,
          target: task.id,
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
          style: { stroke: 'var(--so-border-bright)', strokeWidth: 1.5 },
          label: `${getTaskStatusLabel(taskMap.get(depId)!.status)}`,
          labelStyle: { fontSize: 9, fill: 'var(--so-text-muted)' },
        })
      }
    }
  }

  return { nodes, edges }
}

export function TaskDependencyGraph({ tasks, onSelectTask }: TaskDependencyGraphProps) {
  const { nodes, edges } = useMemo(() => buildGraph(tasks), [tasks])

  if (nodes.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface px-4 py-8 text-center text-sm text-text-muted">
        No task dependencies to visualize.
      </div>
    )
  }

  return (
    <div className="h-[400px] rounded-lg border border-border bg-surface">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={(_event, node) => onSelectTask(node.id)}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.3}
        maxZoom={1.5}
      >
        <Background gap={20} size={1} color="var(--so-border)" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
