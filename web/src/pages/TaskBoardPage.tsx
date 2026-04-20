import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { AnimatePresence } from 'motion/react'
import { getErrorMessage } from '@/utils/errors'
import { AlertTriangle, WifiOff } from 'lucide-react'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { useTaskBoardData } from '@/hooks/useTaskBoardData'
import { useOptimisticUpdate } from '@/hooks/useOptimisticUpdate'
import { useToastStore } from '@/stores/toast'
import {
  type TaskBoardFilters,
  KANBAN_COLUMNS,
  filterTasks,
  groupTasksByColumn,
  canTransitionTo,
} from '@/utils/tasks'
import { TaskBoardSkeleton } from './tasks/TaskBoardSkeleton'
import { TaskColumn } from './tasks/TaskColumn'
import { TaskCard } from './tasks/TaskCard'
import { TaskFilterBar } from './tasks/TaskFilterBar'
import { TaskListView } from './tasks/TaskListView'
import { TaskDetailPanel } from './tasks/TaskDetailPanel'
import { TaskCreateDialog } from './tasks/TaskCreateDialog'
import type { Priority, TaskStatus, TaskType } from '@/api/types/enums'
import type { Task } from '@/api/types/tasks'

const TaskDependencyGraph = lazy(() => import('./tasks/TaskDependencyGraph').then((m) => ({ default: m.TaskDependencyGraph })))

export default function TaskBoardPage() {
  const {
    tasks,
    selectedTask,
    loading,
    error,
    wsConnected,
    wsSetupError,
    fetchTask,
    createTask,
    updateTask,
    transitionTask,
    cancelTask,
    deleteTask,
    optimisticTransition,
  } = useTaskBoardData()

  const [searchParams, setSearchParams] = useSearchParams()
  const [createOpen, setCreateOpen] = useState(false)
  const [showTerminal, setShowTerminal] = useState(false)
  const [showDeps, setShowDeps] = useState(false)
  const [activeTask, setActiveTask] = useState<Task | null>(null)

  const { execute: executeOptimistic } = useOptimisticUpdate()

  // Parse URL params
  const viewMode = searchParams.get('view') === 'list' ? 'list' : 'board'
  const selectedTaskId = searchParams.get('selected')

  // Sync selectedTaskId from URL with store (handles direct navigation / shared links)
  const prevSelectedRef = useRef<string | null>(null)
  const skipNextFetchRef = useRef(false)
  useEffect(() => {
    if (selectedTaskId && selectedTaskId !== prevSelectedRef.current) {
      if (skipNextFetchRef.current) {
        skipNextFetchRef.current = false
      } else {
        fetchTask(selectedTaskId)
      }
    }
    prevSelectedRef.current = selectedTaskId
  }, [selectedTaskId, fetchTask])

  const filters: TaskBoardFilters = useMemo(() => ({
    status: (searchParams.get('status') as TaskStatus) || undefined,
    priority: (searchParams.get('priority') as Priority) || undefined,
    assignee: searchParams.get('assignee') || undefined,
    taskType: (searchParams.get('type') as TaskType) || undefined,
    search: searchParams.get('search') || undefined,
    dateFrom: searchParams.get('dateFrom') || undefined,
    dateTo: searchParams.get('dateTo') || undefined,
  }), [searchParams])

  // Client-side filtering
  const filteredTasks = useMemo(() => filterTasks(tasks, filters), [tasks, filters])

  // Kanban grouping
  const columns = useMemo(() => groupTasksByColumn(filteredTasks), [filteredTasks])

  // Unique assignees for filter dropdown
  const assignees = useMemo(() => {
    const set = new Set<string>()
    for (const task of tasks) {
      if (task.assigned_to) set.add(task.assigned_to)
    }
    return Array.from(set).sort()
  }, [tasks])

  // Filter handling
  const handleFiltersChange = useCallback((newFilters: TaskBoardFilters) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      // Preserve non-filter params
      const view = next.get('view')
      const selected = next.get('selected')
      // Clear all filter params
      next.delete('status')
      next.delete('priority')
      next.delete('assignee')
      next.delete('type')
      next.delete('search')
      next.delete('dateFrom')
      next.delete('dateTo')
      // Set new filter params
      if (newFilters.status) next.set('status', newFilters.status)
      if (newFilters.priority) next.set('priority', newFilters.priority)
      if (newFilters.assignee) next.set('assignee', newFilters.assignee)
      if (newFilters.taskType) next.set('type', newFilters.taskType)
      if (newFilters.search) next.set('search', newFilters.search)
      if (newFilters.dateFrom) next.set('dateFrom', newFilters.dateFrom)
      if (newFilters.dateTo) next.set('dateTo', newFilters.dateTo)
      if (view) next.set('view', view)
      if (selected) next.set('selected', selected)
      return next
    })
  }, [setSearchParams])

  const handleViewModeChange = useCallback((mode: 'board' | 'list') => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (mode === 'list') {
        next.set('view', 'list')
      } else {
        next.delete('view')
      }
      return next
    })
  }, [setSearchParams])

  // Task selection
  const handleSelectTask = useCallback((taskId: string) => {
    skipNextFetchRef.current = true
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('selected', taskId)
      return next
    })
    fetchTask(taskId)
  }, [setSearchParams, fetchTask])

  const handleClosePanel = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('selected')
      return next
    })
  }, [setSearchParams])

  // DnD
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor),
  )

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const task = (event.active.data.current as { task?: Task })?.task
    if (task) setActiveTask(task)
  }, [])

  const handleDragEnd = useCallback(async (event: DragEndEvent) => {
    setActiveTask(null)
    const { active, over } = event
    if (!over) return

    const taskId = active.id as string
    const targetColumnId = over.id as string
    const targetColumn = KANBAN_COLUMNS.find((col) => col.id === targetColumnId)
    if (!targetColumn) return

    const targetStatus = targetColumn.statuses[0]
    if (!targetStatus) return

    const sourceTask = tasks.find((t) => t.id === taskId)
    if (!sourceTask || sourceTask.status === targetStatus) return

    if (!canTransitionTo(sourceTask.status, targetStatus)) {
      useToastStore.getState().add({
        variant: 'warning',
        title: 'Invalid transition',
        description: `Cannot move from "${sourceTask.status}" to "${targetStatus}".`,
      })
      return
    }

    const result = await executeOptimistic(
      () => optimisticTransition(taskId, targetStatus),
      () => transitionTask(taskId, { target_status: targetStatus, expected_version: sourceTask.version }),
    )
    if (result === null) {
      useToastStore.getState().add({ variant: 'error', title: 'Transition failed', description: 'The task could not be moved. It has been reverted.' })
    }
  }, [tasks, optimisticTransition, transitionTask, executeOptimistic])

  // Create task
  const handleCreateTask = useCallback(async (data: Parameters<typeof createTask>[0]) => {
    try {
      await createTask(data)
      useToastStore.getState().add({ variant: 'success', title: 'Task created' })
    } catch (err) {
      useToastStore.getState().add({ variant: 'error', title: 'Failed to create task', description: getErrorMessage(err) })
      throw err
    }
  }, [createTask])

  // Skeleton on initial load
  if (loading && tasks.length === 0) {
    return <TaskBoardSkeleton />
  }

  const visibleColumns = showTerminal
    ? KANBAN_COLUMNS
    : KANBAN_COLUMNS.filter((col) => col.id !== 'terminal')

  return (
    <div className="space-y-section-gap">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Task Board</h1>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-1.5 text-xs text-text-muted">
            <input
              type="checkbox"
              checked={showDeps}
              onChange={(e) => setShowDeps(e.target.checked)}
              className="rounded border-border"
            />
            Dependencies
          </label>
          <label className="flex items-center gap-1.5 text-xs text-text-muted">
            <input
              type="checkbox"
              checked={showTerminal}
              onChange={(e) => setShowTerminal(e.target.checked)}
              className="rounded border-border"
            />
            Show terminal
          </label>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {!wsConnected && !loading && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-card text-sm text-warning">
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      <TaskFilterBar
        filters={filters}
        onFiltersChange={handleFiltersChange}
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        onCreateTask={() => setCreateOpen(true)}
        assignees={assignees}
        taskCount={filteredTasks.length}
      />

      {showDeps && (
        <ErrorBoundary level="section">
          <Suspense fallback={<div className="h-[400px] rounded-lg border border-border bg-surface animate-pulse" />}>
            <TaskDependencyGraph tasks={filteredTasks} onSelectTask={handleSelectTask} />
          </Suspense>
        </ErrorBoundary>
      )}

      <ErrorBoundary level="section">
        {viewMode === 'board' ? (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="flex gap-4 overflow-x-auto pb-4">
              {visibleColumns.map((col) => (
                <TaskColumn
                  key={col.id}
                  column={col}
                  tasks={columns[col.id] ?? []}
                  onSelectTask={handleSelectTask}
                />
              ))}
            </div>
            <DragOverlay>
              {activeTask && (
                <div className="w-72">
                  <TaskCard task={activeTask} onSelect={() => {}} isOverlay />
                </div>
              )}
            </DragOverlay>
          </DndContext>
        ) : (
          <TaskListView
            tasks={filteredTasks}
            onSelectTask={handleSelectTask}
          />
        )}
      </ErrorBoundary>

      {/* Detail panel overlay */}
      <AnimatePresence>
        {selectedTaskId && selectedTask && selectedTask.id === selectedTaskId && (
          <TaskDetailPanel
            task={selectedTask}
            onClose={handleClosePanel}
            onUpdate={async (id, data) => { await updateTask(id, data) }}
            onTransition={async (id, data) => { await transitionTask(id, data) }}
            onCancel={async (id, data) => { await cancelTask(id, data) }}
            onDelete={async (id) => { await deleteTask(id) }}
          />
        )}
      </AnimatePresence>

      {/* Create dialog */}
      <TaskCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreate={handleCreateTask}
      />
    </div>
  )
}
