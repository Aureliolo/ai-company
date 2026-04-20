/** System health and per-agent autonomy level types. */

import type { AutonomyLevel } from './enums'

export type TelemetryStatus = 'enabled' | 'disabled'

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'down'
  persistence: boolean | null
  message_bus: boolean | null
  telemetry: TelemetryStatus
  version: string
  uptime_seconds: number
}

export interface AutonomyLevelResponse {
  agent_id: string
  level: AutonomyLevel
  promotion_pending: boolean
}

export interface AutonomyLevelRequest {
  level: AutonomyLevel
}
