/** Task domain types. */

import type {
  Complexity,
  CoordinationTopology,
  Priority,
  TaskSource,
  TaskStatus,
  TaskStructure,
  TaskType,
} from './enums'

export interface AcceptanceCriterion {
  description: string
  met: boolean
}

export interface ExpectedArtifact {
  name: string
  type: string
}

export interface Task {
  id: string
  title: string
  description: string
  type: TaskType
  status: TaskStatus
  priority: Priority
  project: string
  created_by: string
  assigned_to: string | null
  readonly reviewers: readonly string[]
  readonly dependencies: readonly string[]
  readonly artifacts_expected: readonly ExpectedArtifact[]
  readonly acceptance_criteria: readonly AcceptanceCriterion[]
  estimated_complexity: Complexity
  budget_limit: number
  cost?: number
  deadline: string | null
  max_retries: number
  parent_task_id: string | null
  readonly delegation_chain: readonly string[]
  task_structure: TaskStructure | null
  coordination_topology: CoordinationTopology
  source?: TaskSource | null
  version?: number
  created_at?: string
  updated_at?: string
}

export interface CreateTaskRequest {
  title: string
  description: string
  type: TaskType
  priority?: Priority
  project: string
  created_by: string
  assigned_to?: string | null
  estimated_complexity?: Complexity
  budget_limit?: number
}

export interface UpdateTaskRequest {
  title?: string
  description?: string
  priority?: Priority
  assigned_to?: string | null
  budget_limit?: number
  expected_version?: number
}

export interface TransitionTaskRequest {
  target_status: TaskStatus
  assigned_to?: string | null
  expected_version?: number
}

export interface CancelTaskRequest {
  reason: string
}

export interface TaskFilters {
  status?: TaskStatus
  assigned_to?: string
  project?: string
  offset?: number
  limit?: number
}
