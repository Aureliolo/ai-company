import { apiClient, unwrap } from '../client'
import type { ApiResponse, PaginatedResponse } from '../types/http'

// -- Response types ----------------------------------------------------------

export interface ScalingStrategyResponse {
  name: string
  enabled: boolean
  priority: number
}

export interface ScalingSignalResponse {
  name: string
  value: number
  source: string
  threshold: number | null
  timestamp: string
}

export interface ScalingDecisionResponse {
  id: string
  action_type: string
  source_strategy: string
  target_agent_id: string | null
  target_role: string | null
  target_skills: readonly string[]
  target_department: string | null
  rationale: string
  confidence: number
  signals: readonly ScalingSignalResponse[]
  created_at: string
}

// -- API functions -----------------------------------------------------------

export async function getScalingStrategies(): Promise<ScalingStrategyResponse[]> {
  const response = await apiClient.get<ApiResponse<ScalingStrategyResponse[]>>(
    '/scaling/strategies',
  )
  return unwrap(response)
}

export async function getScalingDecisions(params?: {
  offset?: number
  limit?: number
}): Promise<{ data: ScalingDecisionResponse[]; total: number }> {
  const response = await apiClient.get<
    PaginatedResponse<ScalingDecisionResponse>
  >('/scaling/decisions', { params })
  const body = response.data
  if (
    !body.pagination ||
    typeof body.pagination.total !== 'number'
  ) {
    throw new Error(
      'Invalid paginated response: missing pagination.total field',
    )
  }
  return {
    data: body.data ?? [],
    total: body.pagination.total,
  }
}

export async function getScalingSignals(): Promise<ScalingSignalResponse[]> {
  const response = await apiClient.get<ApiResponse<ScalingSignalResponse[]>>(
    '/scaling/signals',
  )
  return unwrap(response)
}

export async function triggerScalingEvaluation(): Promise<
  ScalingDecisionResponse[]
> {
  const response = await apiClient.post<ApiResponse<ScalingDecisionResponse[]>>(
    '/scaling/evaluate',
  )
  return unwrap(response)
}
