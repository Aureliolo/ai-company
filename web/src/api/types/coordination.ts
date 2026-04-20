/** Multi-agent coordination request/response types. */

import type { CoordinationTopology } from './enums'

export interface CoordinateTaskRequest {
  agent_names?: string[] | null
  max_subtasks?: number
  max_concurrency_per_wave?: number | null
  fail_fast?: boolean | null
}

export interface CoordinationPhaseResponse {
  phase: string
  success: boolean
  duration_seconds: number
  error: string | null
}

export interface CoordinationResultResponse {
  parent_task_id: string
  topology: CoordinationTopology
  total_duration_seconds: number
  total_cost: number
  currency: string
  readonly phases: readonly CoordinationPhaseResponse[]
  wave_count: number
  is_success: boolean
}
