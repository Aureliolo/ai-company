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
  /** Opaque pagination cursor from the previous response's `pagination.next_cursor`. */
  cursor?: string | null
  limit?: number
}): Promise<{
  data: ScalingDecisionResponse[]
  total: number | null
  nextCursor: string | null
  hasMore: boolean
}> {
  const response = await apiClient.get<
    PaginatedResponse<ScalingDecisionResponse>
  >('/scaling/decisions', { params })
  const body = response.data
  if (!body.pagination) {
    throw new Error('Invalid paginated response: missing pagination envelope')
  }
  return {
    data: body.data ?? [],
    total: body.pagination.total,
    nextCursor: body.pagination.next_cursor,
    hasMore: body.pagination.has_more,
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
