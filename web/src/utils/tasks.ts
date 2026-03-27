import type { Priority, Task, TaskStatus, TaskType } from '@/api/types'
import type { SemanticColor } from '@/lib/utils'

// ── Status color mapping ────────────────────────────────────

const TASK_STATUS_COLOR_MAP: Record<TaskStatus, SemanticColor | 'text-secondary'> = {
  created: 'text-secondary',
  assigned: 'accent',
  in_progress: 'accent',
  in_review: 'warning',
  completed: 'success',
  blocked: 'danger',
  failed: 'danger',
  interrupted: 'warning',
  cancelled: 'text-secondary',
}

export function getTaskStatusColor(status: TaskStatus): SemanticColor | 'text-secondary' {
  return TASK_STATUS_COLOR_MAP[status]
}

// ── Status labels ───────────────────────────────────────────

const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  created: 'Created',
  assigned: 'Assigned',
  in_progress: 'In Progress',
  in_review: 'In Review',
  completed: 'Completed',
  blocked: 'Blocked',
  failed: 'Failed',
  interrupted: 'Interrupted',
  cancelled: 'Cancelled',
}

export function getTaskStatusLabel(status: TaskStatus): string {
  return TASK_STATUS_LABELS[status]
}

// ── Priority color mapping ──────────────────────────────────

const PRIORITY_COLOR_MAP: Record<Priority, SemanticColor | 'text-secondary'> = {
  critical: 'danger',
  high: 'warning',
  medium: 'accent',
  low: 'text-secondary',
}

export function getPriorityColor(priority: Priority): SemanticColor | 'text-secondary' {
  return PRIORITY_COLOR_MAP[priority]
}

// ── Priority labels ─────────────────────────────────────────

const PRIORITY_LABELS: Record<Priority, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

export function getPriorityLabel(priority: Priority): string {
  return PRIORITY_LABELS[priority]
}

// ── Kanban column definitions ───────────────────────────────

export type KanbanColumnId =
  | 'backlog'
  | 'ready'
  | 'in_progress'
  | 'in_review'
  | 'done'
  | 'blocked'
  | 'terminal'

export interface KanbanColumn {
  readonly id: KanbanColumnId
  readonly label: string
  readonly statuses: readonly TaskStatus[]
  readonly color: SemanticColor | 'text-secondary'
}

export const KANBAN_COLUMNS: readonly KanbanColumn[] = [
  { id: 'backlog', label: 'Backlog', statuses: ['created'], color: 'text-secondary' },
  { id: 'ready', label: 'Ready', statuses: ['assigned'], color: 'accent' },
  { id: 'in_progress', label: 'In Progress', statuses: ['in_progress'], color: 'accent' },
  { id: 'in_review', label: 'In Review', statuses: ['in_review'], color: 'warning' },
  { id: 'done', label: 'Done', statuses: ['completed'], color: 'success' },
  { id: 'blocked', label: 'Blocked', statuses: ['blocked'], color: 'danger' },
  { id: 'terminal', label: 'Terminal', statuses: ['failed', 'interrupted', 'cancelled'], color: 'text-secondary' },
] as const

export const STATUS_TO_COLUMN: Record<TaskStatus, KanbanColumnId> = Object.fromEntries(
  KANBAN_COLUMNS.flatMap((col) =>
    col.statuses.map((status) => [status, col.id]),
  ),
) as Record<TaskStatus, KanbanColumnId>

// ── Group tasks by column ───────────────────────────────────

export function groupTasksByColumn(tasks: readonly Task[]): Record<KanbanColumnId, Task[]> {
  const grouped: Record<KanbanColumnId, Task[]> = {
    backlog: [],
    ready: [],
    in_progress: [],
    in_review: [],
    done: [],
    blocked: [],
    terminal: [],
  }

  for (const task of tasks) {
    const columnId = STATUS_TO_COLUMN[task.status]
    grouped[columnId].push(task)
  }

  return grouped
}

// ── Client-side filtering ───────────────────────────────────

export interface TaskBoardFilters {
  status?: TaskStatus
  priority?: Priority
  assignee?: string
  taskType?: TaskType
  search?: string
}

export function filterTasks(tasks: readonly Task[], filters: TaskBoardFilters): Task[] {
  let result = tasks as Task[]

  if (filters.status) {
    result = result.filter((t) => t.status === filters.status)
  }

  if (filters.priority) {
    result = result.filter((t) => t.priority === filters.priority)
  }

  if (filters.assignee) {
    result = result.filter((t) => t.assigned_to === filters.assignee)
  }

  if (filters.taskType) {
    result = result.filter((t) => t.type === filters.taskType)
  }

  if (filters.search) {
    const query = filters.search.toLowerCase()
    result = result.filter(
      (t) =>
        t.title.toLowerCase().includes(query) ||
        t.description.toLowerCase().includes(query),
    )
  }

  return result
}

// ── Status transition validation ────────────────────────────

export const VALID_TRANSITIONS: Record<TaskStatus, readonly TaskStatus[]> = {
  created: ['assigned'],
  assigned: ['in_progress', 'failed', 'blocked', 'cancelled', 'interrupted'],
  in_progress: ['in_review', 'failed', 'cancelled', 'interrupted'],
  in_review: ['completed', 'in_progress'],
  completed: [],
  blocked: ['assigned'],
  failed: ['assigned'],
  interrupted: ['assigned'],
  cancelled: [],
}

export function canTransitionTo(currentStatus: TaskStatus, targetStatus: TaskStatus): boolean {
  return VALID_TRANSITIONS[currentStatus].includes(targetStatus)
}

export function getAvailableTransitions(status: TaskStatus): readonly TaskStatus[] {
  return VALID_TRANSITIONS[status]
}
