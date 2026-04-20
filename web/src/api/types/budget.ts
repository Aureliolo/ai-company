/** Budget, cost tracking and spending types. */

/** Mirrors `synthorg.core.enums.FinishReason`. */
export type FinishReason =
  | 'stop'
  | 'max_tokens'
  | 'tool_use'
  | 'content_filter'
  | 'error'

export interface CostRecord {
  agent_id: string
  task_id: string
  project_id: string | null
  provider: string
  model: string
  input_tokens: number
  output_tokens: number
  cost: number
  timestamp: string
  call_category: 'productive' | 'coordination' | 'system' | 'embedding' | null
  /** Quality-vs-cost ratio for the call, when measurable. */
  accuracy_effort_ratio: number | null
  /** Observed provider latency in milliseconds. */
  latency_ms: number | null
  /** Whether the response was served from a cache layer. */
  cache_hit: boolean | null
  /**
   * Number of automatic retries performed before success / failure.
   * Implies `retry_reason` is populated when > 0.
   */
  retry_count: number | null
  /** Retry trigger (e.g. `rate_limit`, `timeout`). */
  retry_reason: string | null
  /** Provider finish reason (mirrors backend `FinishReason` enum). */
  finish_reason: FinishReason | null
  /** Whether the call completed without error. */
  success: boolean | null
}

export interface DailySummary {
  date: string
  total_cost: number
  total_input_tokens: number
  total_output_tokens: number
  record_count: number
  currency: string
}

export interface PeriodSummary {
  avg_cost: number
  total_cost: number
  total_input_tokens: number
  total_output_tokens: number
  record_count: number
  currency: string
}

export interface BudgetAlertConfig {
  warn_at: number
  critical_at: number
  hard_stop_at: number
}

export interface AutoDowngradeConfig {
  enabled: boolean
  threshold: number
  readonly downgrade_map: readonly [string, string][]
  boundary: 'task_assignment'
}

export interface BudgetConfig {
  total_monthly: number
  alerts: BudgetAlertConfig
  per_task_limit: number
  per_agent_daily_limit: number
  auto_downgrade: AutoDowngradeConfig
  reset_day: number
  currency: string
}

export interface AgentSpending {
  agent_id: string
  total_cost: number
  currency: string
}
