import { apiClient, unwrapPaginated, type PaginatedResult } from '../client'
import type { ActivityEvent, ActivityEventType, PaginatedResponse, PaginationParams } from '../types'

export interface ActivityFilterParams extends PaginationParams {
  type?: ActivityEventType
  agent_id?: string
  last_n_hours?: 24 | 48 | 168
}

export async function listActivities(
  params?: ActivityFilterParams,
): Promise<PaginatedResult<ActivityEvent>> {
  const response = await apiClient.get<PaginatedResponse<ActivityEvent>>('/activities', { params })
  return unwrapPaginated<ActivityEvent>(response)
}
