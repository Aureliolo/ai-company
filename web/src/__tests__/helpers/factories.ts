import type { Task } from '@/api/types'

export function makeTask(id: string, overrides?: Partial<Task>): Task
export function makeTask(id: string, title: string, overrides?: Partial<Task>): Task
export function makeTask(id: string, titleOrOverrides?: string | Partial<Task>, overrides?: Partial<Task>): Task {
  const title = typeof titleOrOverrides === 'string' ? titleOrOverrides : `Task ${id}`
  const finalOverrides = typeof titleOrOverrides === 'object' ? titleOrOverrides : overrides
  return {
    id,
    title,
    description: 'Description',
    type: 'development',
    status: 'assigned',
    priority: 'medium',
    project: 'test-project',
    created_by: 'agent-cto',
    assigned_to: 'agent-eng',
    reviewers: [],
    dependencies: [],
    artifacts_expected: [],
    acceptance_criteria: [],
    estimated_complexity: 'medium',
    budget_limit: 10,
    deadline: null,
    max_retries: 3,
    parent_task_id: null,
    delegation_chain: [],
    task_structure: null,
    coordination_topology: 'auto',
    version: 1,
    created_at: '2026-03-20T10:00:00Z',
    updated_at: '2026-03-25T14:00:00Z',
    ...finalOverrides,
  }
}
