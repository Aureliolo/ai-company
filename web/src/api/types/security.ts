/** Control-plane query types: tool audit, agent trust and security export. */

import type { TrendDirection } from './agents'
import type { AgentStatus, ApprovalRiskLevel, ToolAccessLevel } from './enums'

export type ToolCategory =
  | 'file_system'
  | 'code_execution'
  | 'version_control'
  | 'web'
  | 'database'
  | 'terminal'
  | 'design'
  | 'communication'
  | 'analytics'
  | 'deployment'
  | 'memory'
  | 'mcp'
  | 'other'

export type AuditVerdictStr = 'allow' | 'deny' | 'escalate' | 'output_scan'

export interface TrustSummary {
  readonly level: ToolAccessLevel
  readonly score: number | null
  readonly last_evaluated_at: string | null
}

export interface PerformanceSummary {
  readonly quality_score: number | null
  readonly collaboration_score: number | null
  readonly trend: TrendDirection | null
}

export interface AgentHealthResponse {
  readonly agent_id: string
  readonly agent_name: string
  readonly lifecycle_status: AgentStatus
  readonly last_active_at: string | null
  readonly trust: TrustSummary | null
  readonly performance: PerformanceSummary | null
}

export interface AuditEntry {
  readonly id: string
  readonly timestamp: string
  readonly agent_id: string | null
  readonly task_id: string | null
  readonly tool_name: string
  readonly tool_category: ToolCategory
  readonly action_type: string
  readonly arguments_hash: string
  readonly verdict: AuditVerdictStr
  readonly risk_level: ApprovalRiskLevel
  readonly reason: string
  readonly matched_rules: readonly string[]
  readonly evaluation_duration_ms: number
  readonly confidence: 'high' | 'low'
  readonly approval_id: string | null
}

export interface MessageOverheadPayload {
  readonly team_size: number
  readonly message_count: number
  readonly is_quadratic: boolean
}

export interface CoordinationMetricsPayload {
  readonly coordination_efficiency: Record<string, unknown>
  readonly coordination_overhead: Record<string, unknown>
  readonly error_amplification: Record<string, unknown>
  readonly message_density: Record<string, unknown>
  readonly redundancy_rate: Record<string, unknown>
  readonly amdahl_ceiling: Record<string, unknown>
  readonly straggler_gap: Record<string, unknown>
  readonly token_speedup_ratio: Record<string, unknown>
  readonly message_overhead: MessageOverheadPayload
}

export interface CoordinationMetricsRecord {
  readonly task_id: string
  readonly agent_id: string | null
  readonly computed_at: string
  readonly team_size: number
  readonly metrics: CoordinationMetricsPayload
}

export interface SecurityConfigExportResponse {
  readonly config: Record<string, unknown>
  readonly exported_at: string
  readonly custom_policies_warning: string | null
}
