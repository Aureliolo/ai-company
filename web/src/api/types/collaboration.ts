/** Collaboration scoring, overrides and LLM calibration types. */

export interface CollaborationScoreResult {
  score: number
  strategy_name: string
  readonly component_scores: readonly [string, number][]
  confidence: number
  override_active: boolean
}

export interface SetOverrideRequest {
  score: number
  reason: string
  expires_in_days?: number | null
}

export interface OverrideResponse {
  agent_id: string
  score: number
  reason: string
  applied_by: string
  applied_at: string
  expires_at: string | null
}

export interface LlmCalibrationRecord {
  id: string
  agent_id: string
  sampled_at: string
  interaction_record_id: string
  llm_score: number
  behavioral_score: number
  drift: number
  rationale: string
  model_used: string
  cost: number
}

export interface CalibrationSummaryResponse {
  agent_id: string
  average_drift: number | null
  readonly records: readonly LlmCalibrationRecord[]
  record_count: number
}
