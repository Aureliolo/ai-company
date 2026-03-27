import { apiClient, unwrapPaginated, type PaginatedResult } from '../client'
import type { ActivityItem, PaginatedResponse, PaginationParams } from '../types'

export async function listActivities(
  params?: PaginationParams,
): Promise<PaginatedResult<ActivityItem>> {
  const response = await apiClient.get<PaginatedResponse<ActivityItem>>('/activities', { params })
  return unwrapPaginated<ActivityItem>(response)
}
