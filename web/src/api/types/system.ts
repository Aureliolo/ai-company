/** System health and per-agent autonomy level types. */

import type { AutonomyLevel } from './enums'

export type TelemetryStatus = 'enabled' | 'disabled'

/** Binary readiness outcome from ``/api/v1/readyz``. */
export type ReadinessOutcome = 'ok' | 'unavailable'

/** Liveness response from ``/api/v1/healthz`` -- always ``status: 'ok'``. */
export interface LivenessStatus {
  status: 'ok'
  version: string
  uptime_seconds: number
}

/**
 * Readiness response from ``/api/v1/readyz`` -- ``status`` is binary
 * (``ok`` / ``unavailable``). HTTP 200 when ok, 503 when unavailable.
 */
export interface ReadinessStatus {
  status: ReadinessOutcome
  persistence: boolean | null
  message_bus: boolean | null
  telemetry: TelemetryStatus
  version: string
  uptime_seconds: number
}

/**
 * Legacy alias for callers that still import `HealthStatus`.  New
 * code should use :type:`ReadinessStatus` / :type:`LivenessStatus`
 * directly so the liveness vs readiness split is explicit.
 */
export type HealthStatus = ReadinessStatus

export interface AutonomyLevelResponse {
  agent_id: string
  level: AutonomyLevel
  promotion_pending: boolean
}

export interface AutonomyLevelRequest {
  level: AutonomyLevel
}
