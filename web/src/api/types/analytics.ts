/** Analytics metrics, trends, forecasts, activity feed and department health. */

import type { ActivityEventType } from './agents'
import type { DepartmentName, TaskStatus } from './enums'
import type { WsEventType } from './websocket'

export type TrendPeriod = '7d' | '30d' | '90d'

export type TrendMetric = 'spend' | 'tasks_completed' | 'success_rate' | 'active_agents'

export type BucketSize = 'hour' | 'day'

export interface TrendDataPoint {
  timestamp: string
  value: number
}

export interface OverviewMetrics {
  total_tasks: number
  tasks_by_status: Record<TaskStatus, number>
  total_agents: number
  total_cost: number
  budget_remaining: number
  budget_used_percent: number
  cost_7d_trend: readonly TrendDataPoint[]
  active_agents_count: number
  idle_agents_count: number
  currency: string
}

export interface TrendsResponse {
  period: TrendPeriod
  metric: TrendMetric
  bucket_size: BucketSize
  readonly data_points: readonly TrendDataPoint[]
}

export interface ForecastPoint {
  day: string
  projected_spend: number
}

export interface ForecastResponse {
  horizon_days: number
  projected_total: number
  readonly daily_projections: readonly ForecastPoint[]
  days_until_exhausted: number | null
  confidence: number
  avg_daily_spend: number
  currency: string
}

/** Activity event as returned by the backend REST API. */
export interface ActivityEvent {
  event_type: ActivityEventType
  timestamp: string
  description: string
  related_ids: Record<string, string>
}

/**
 * Legacy display-oriented activity item derived from {@link ActivityEvent}.
 * Used by the dashboard ActivityFeed component.
 */
export interface ActivityItem {
  id: string
  timestamp: string
  agent_name: string
  /** REST path produces ActivityEventType; WS path produces WsEventType. */
  action_type: ActivityEventType | WsEventType
  description: string
  task_id: string | null
  department: DepartmentName | null
}

/**
 * Department-level health aggregation as returned by the backend.
 * Matches the Pydantic DepartmentHealth model in controllers/departments.py.
 */
export interface DepartmentHealth {
  department_name: DepartmentName
  agent_count: number
  active_agent_count: number
  /** ISO 4217 currency code (e.g. "EUR", "USD"). */
  currency: string
  /** Mean quality score across agents, 0.0 to 10.0, or null when insufficient data. */
  avg_performance_score: number | null
  department_cost_7d: number
  readonly cost_trend: readonly TrendDataPoint[]
  /** Mean collaboration score, 0.0 to 10.0, or null when insufficient data. */
  collaboration_score: number | null
  /** Backend-computed: active_agent_count / agent_count * 100. */
  utilization_percent: number
}
