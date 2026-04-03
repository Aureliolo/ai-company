import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import { ClipboardList } from 'lucide-react'
import { PriorityBadge } from '@/components/ui/task-status-indicator'
import { cn } from '@/lib/utils'
import type { Priority } from '@/api/types'

export interface TaskNodeData extends Record<string, unknown> {
  label: string
  config: Record<string, unknown>
  selected?: boolean
  hasError?: boolean
}

export type TaskNodeType = Node<TaskNodeData, 'task'>

const VALID_PRIORITIES = new Set<string>(['critical', 'high', 'medium', 'low'])

function TaskNodeComponent({ data, selected }: NodeProps<TaskNodeType>) {
  const title = (data.config?.title as string) || data.label
  const rawPriority = data.config?.priority as string | undefined
  const priority = rawPriority && VALID_PRIORITIES.has(rawPriority) ? (rawPriority as Priority) : undefined
  const taskType = (data.config?.task_type as string) || undefined

  return (
    <div
      className={cn(
        'min-w-40 max-w-56 rounded-lg border border-border bg-card px-3 py-2',
        selected && 'ring-2 ring-accent',
        data.hasError && 'ring-2 ring-danger',
      )}
      data-testid="task-node"
      aria-label={`Task: ${title}`}
    >
      <Handle type="target" position={Position.Top} className="bg-border-bright! size-1.5!" />

      <div className="flex items-start gap-2">
        <ClipboardList className="mt-0.5 size-3.5 shrink-0 text-accent" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="truncate font-sans text-xs font-semibold text-foreground">
              {title}
            </span>
            {priority && <PriorityBadge priority={priority} />}
          </div>
          {taskType && (
            <span className="block truncate font-sans text-micro text-muted-foreground">
              {taskType}
            </span>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="bg-border-bright! size-1.5!" />
    </div>
  )
}

export const TaskNode = memo(TaskNodeComponent)
