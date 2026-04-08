import { describe, expect, it } from 'vitest'
import type { Priority, Task, TaskStatus } from '@/api/types'
import {
  KANBAN_COLUMNS,
  OFF_BOARD_STATUSES,
  STATUS_TO_COLUMN,
  VALID_TRANSITIONS,
  canTransitionTo,
  filterTasks,
  getAvailableTransitions,
  getPriorityColor,
  getPriorityLabel,
  getTaskStatusColor,
  getTaskStatusLabel,
  groupTasksByColumn,
} from '@/utils/tasks'
import { makeTask as makeTaskFactory } from '../helpers/factories'

// ── Helpers ─────────────────────────────────────────────────

function makeTask(overrides: Partial<Task> = {}): Task {
  return makeTaskFactory('task-1', { title: 'Test task', description: 'A test task description', ...overrides })
}

const ALL_STATUSES: TaskStatus[] = [
  'created', 'assigned', 'in_progress', 'in_review', 'completed',
  'blocked', 'failed', 'interrupted', 'suspended', 'cancelled',
]

// ── getTaskStatusColor ──────────────────────────────────────

describe('getTaskStatusColor', () => {
  it.each<[TaskStatus, string]>([
    ['created', 'text-secondary'],
    ['assigned', 'accent'],
    ['in_progress', 'accent'],
    ['in_review', 'warning'],
    ['completed', 'success'],
    ['blocked', 'danger'],
    ['failed', 'danger'],
    ['interrupted', 'warning'],
    ['suspended', 'warning'],
    ['cancelled', 'text-secondary'],
  ])('maps %s to %s', (status, expected) => {
    expect(getTaskStatusColor(status)).toBe(expected)
  })
})

// ── getTaskStatusLabel ──────────────────────────────────────

describe('getTaskStatusLabel', () => {
  it.each<[TaskStatus, string]>([
    ['created', 'Created'],
    ['assigned', 'Assigned'],
    ['in_progress', 'In Progress'],
    ['in_review', 'In Review'],
    ['completed', 'Completed'],
    ['blocked', 'Blocked'],
    ['failed', 'Failed'],
    ['interrupted', 'Interrupted'],
    ['suspended', 'Suspended'],
    ['cancelled', 'Cancelled'],
  ])('maps %s to %s', (status, expected) => {
    expect(getTaskStatusLabel(status)).toBe(expected)
  })
})

// ── getPriorityColor ────────────────────────────────────────

describe('getPriorityColor', () => {
  it.each<[Priority, string]>([
    ['critical', 'danger'],
    ['high', 'warning'],
    ['medium', 'accent'],
    ['low', 'text-secondary'],
  ])('maps %s to %s', (priority, expected) => {
    expect(getPriorityColor(priority)).toBe(expected)
  })
})

// ── getPriorityLabel ────────────────────────────────────────

describe('getPriorityLabel', () => {
  it.each<[Priority, string]>([
    ['critical', 'Critical'],
    ['high', 'High'],
    ['medium', 'Medium'],
    ['low', 'Low'],
  ])('maps %s to %s', (priority, expected) => {
    expect(getPriorityLabel(priority)).toBe(expected)
  })
})

// ── KANBAN_COLUMNS ──────────────────────────────────────────

describe('KANBAN_COLUMNS', () => {
  it('defines 7 columns', () => {
    expect(KANBAN_COLUMNS).toHaveLength(7)
  })

  it('covers all on-board task statuses exactly once', () => {
    const onBoard = ALL_STATUSES.filter((s) => !OFF_BOARD_STATUSES.has(s))
    const allStatuses = KANBAN_COLUMNS.flatMap((col) => col.statuses)
    expect(allStatuses).toHaveLength(onBoard.length)
    for (const status of onBoard) {
      expect(allStatuses).toContain(status)
    }
  })

  it('has unique column IDs', () => {
    const ids = KANBAN_COLUMNS.map((col) => col.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})

// ── STATUS_TO_COLUMN ────────────────────────────────────────

describe('STATUS_TO_COLUMN', () => {
  it('maps every on-board TaskStatus to a column', () => {
    for (const status of ALL_STATUSES) {
      if (OFF_BOARD_STATUSES.has(status)) {
        expect(STATUS_TO_COLUMN[status]).toBeNull()
      } else {
        expect(STATUS_TO_COLUMN[status]).toBeDefined()
      }
    }
  })

  it('is consistent with KANBAN_COLUMNS', () => {
    for (const col of KANBAN_COLUMNS) {
      for (const status of col.statuses) {
        expect(STATUS_TO_COLUMN[status]).toBe(col.id)
      }
    }
  })
})

// ── groupTasksByColumn ──────────────────────────────────────

describe('groupTasksByColumn', () => {
  it('groups tasks into correct columns', () => {
    const tasks = [
      makeTask({ id: 't1', status: 'created' }),
      makeTask({ id: 't2', status: 'assigned' }),
      makeTask({ id: 't3', status: 'in_progress' }),
      makeTask({ id: 't4', status: 'completed' }),
    ]
    const grouped = groupTasksByColumn(tasks)
    expect(grouped.backlog).toHaveLength(1)
    expect(grouped.ready).toHaveLength(1)
    expect(grouped.in_progress).toHaveLength(1)
    expect(grouped.done).toHaveLength(1)
    expect(grouped.in_review).toHaveLength(0)
    expect(grouped.blocked).toHaveLength(0)
    expect(grouped.terminal).toHaveLength(0)
  })

  it('groups terminal statuses together', () => {
    const tasks = [
      makeTask({ id: 't1', status: 'failed' }),
      makeTask({ id: 't2', status: 'interrupted' }),
      makeTask({ id: 't3', status: 'cancelled' }),
    ]
    const grouped = groupTasksByColumn(tasks)
    expect(grouped.terminal).toHaveLength(3)
  })

  it('returns empty arrays for all columns when no tasks', () => {
    const grouped = groupTasksByColumn([])
    for (const col of KANBAN_COLUMNS) {
      expect(grouped[col.id]).toHaveLength(0)
    }
  })

  it('preserves all on-board tasks (off-board excluded)', () => {
    const tasks = ALL_STATUSES.map((status, i) =>
      makeTask({ id: `t${i}`, status }),
    )
    const grouped = groupTasksByColumn(tasks)
    const total = Object.values(grouped).reduce((sum, arr) => sum + arr.length, 0)
    const onBoardCount = ALL_STATUSES.filter((s) => !OFF_BOARD_STATUSES.has(s)).length
    expect(total).toBe(onBoardCount)
  })
})

// ── filterTasks ─────────────────────────────────────────────

describe('filterTasks', () => {
  const tasks = [
    makeTask({ id: 't1', status: 'assigned', priority: 'high', assigned_to: 'agent-a', type: 'development', title: 'Build API' }),
    makeTask({ id: 't2', status: 'in_progress', priority: 'medium', assigned_to: 'agent-b', type: 'design', title: 'Design UI' }),
    makeTask({ id: 't3', status: 'completed', priority: 'low', assigned_to: 'agent-a', type: 'research', title: 'Research tools' }),
    makeTask({ id: 't4', status: 'blocked', priority: 'critical', assigned_to: null, type: 'review', title: 'Review PR' }),
  ]

  it('returns all tasks with empty filters', () => {
    expect(filterTasks(tasks, {})).toHaveLength(4)
  })

  it('filters by status', () => {
    const result = filterTasks(tasks, { status: 'assigned' })
    expect(result).toHaveLength(1)
    expect(result[0]!.id).toBe('t1')
  })

  it('filters by priority', () => {
    const result = filterTasks(tasks, { priority: 'critical' })
    expect(result).toHaveLength(1)
    expect(result[0]!.id).toBe('t4')
  })

  it('filters by assignee', () => {
    const result = filterTasks(tasks, { assignee: 'agent-a' })
    expect(result).toHaveLength(2)
  })

  it('filters by task type', () => {
    const result = filterTasks(tasks, { taskType: 'design' })
    expect(result).toHaveLength(1)
    expect(result[0]!.id).toBe('t2')
  })

  it('filters by search (case-insensitive, matches title)', () => {
    const result = filterTasks(tasks, { search: 'api' })
    expect(result).toHaveLength(1)
    expect(result[0]!.id).toBe('t1')
  })

  it('filters by search (matches description)', () => {
    const result = filterTasks(tasks, { search: 'test task' })
    expect(result).toHaveLength(4) // all have "A test task description"
  })

  it('combines multiple filters with AND logic', () => {
    const result = filterTasks(tasks, { assignee: 'agent-a', priority: 'high' })
    expect(result).toHaveLength(1)
    expect(result[0]!.id).toBe('t1')
  })

  it('returns empty array when no tasks match', () => {
    const result = filterTasks(tasks, { assignee: 'nonexistent' })
    expect(result).toHaveLength(0)
  })

  it('handles empty task list', () => {
    expect(filterTasks([], { status: 'assigned' })).toHaveLength(0)
  })

  it('handles search with empty description', () => {
    const tasksWithEmpty = [
      makeTask({ id: 't1', title: 'Find me', description: '' }),
    ]
    const result = filterTasks(tasksWithEmpty, { search: 'find' })
    expect(result).toHaveLength(1)
    expect(result[0]!.id).toBe('t1')
  })

  it('search does not crash on empty description', () => {
    const tasksWithEmpty = [
      makeTask({ id: 't1', description: '' }),
    ]
    expect(() => filterTasks(tasksWithEmpty, { search: 'anything' })).not.toThrow()
  })
})

// ── VALID_TRANSITIONS ───────────────────────────────────────

describe('VALID_TRANSITIONS', () => {
  it('defines transitions for every status', () => {
    for (const status of ALL_STATUSES) {
      expect(VALID_TRANSITIONS[status]).toBeDefined()
      expect(Array.isArray(VALID_TRANSITIONS[status])).toBe(true)
    }
  })

  it('terminal statuses have no outgoing transitions', () => {
    expect(VALID_TRANSITIONS.completed).toHaveLength(0)
    expect(VALID_TRANSITIONS.cancelled).toHaveLength(0)
  })

  it('created can transition to assigned', () => {
    expect(VALID_TRANSITIONS.created).toContain('assigned')
  })

  it('in_progress can transition to in_review', () => {
    expect(VALID_TRANSITIONS.in_progress).toContain('in_review')
  })

  it('blocked can transition to assigned', () => {
    expect(VALID_TRANSITIONS.blocked).toContain('assigned')
  })
})

// ── canTransitionTo ─────────────────────────────────────────

describe('canTransitionTo', () => {
  it('returns true for valid transitions', () => {
    expect(canTransitionTo('created', 'assigned')).toBe(true)
    expect(canTransitionTo('assigned', 'in_progress')).toBe(true)
    expect(canTransitionTo('in_progress', 'in_review')).toBe(true)
    expect(canTransitionTo('in_review', 'completed')).toBe(true)
  })

  it('returns false for invalid transitions', () => {
    expect(canTransitionTo('created', 'completed')).toBe(false)
    expect(canTransitionTo('completed', 'created')).toBe(false)
    expect(canTransitionTo('cancelled', 'assigned')).toBe(false)
  })

  it('returns false for same-status transition', () => {
    expect(canTransitionTo('assigned', 'assigned')).toBe(false)
  })
})

// ── getAvailableTransitions ────────────────────────────────

describe('getAvailableTransitions', () => {
  it('returns valid transitions for a status', () => {
    const transitions = getAvailableTransitions('assigned')
    expect(transitions.length).toBeGreaterThan(0)
    for (const t of transitions) {
      expect(canTransitionTo('assigned', t)).toBe(true)
    }
  })

  it('returns empty array for terminal statuses', () => {
    expect(getAvailableTransitions('completed')).toHaveLength(0)
    expect(getAvailableTransitions('cancelled')).toHaveLength(0)
  })
})
