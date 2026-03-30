import { apiClient, unwrapPaginated, type PaginatedResult } from '../client'
import type { ActivityEvent, ActivityEventType, ActivityItem, PaginatedResponse, PaginationParams } from '../types'

export interface ActivityFilterParams extends PaginationParams {
  type?: ActivityEventType
  agent_id?: string
  last_n_hours?: 24 | 48 | 168
}

/** Map a REST ActivityEvent to the display-oriented ActivityItem shape. */
export function mapActivityEventToItem(event: ActivityEvent): ActivityItem {
  return {
    id: event.related_ids.task_id ?? event.related_ids.agent_id ?? event.timestamp,
    timestamp: event.timestamp,
    agent_name: event.related_ids.agent_name ?? event.related_ids.agent_id ?? 'System',
    action_type: event.event_type,
    description: event.description,
    task_id: event.related_ids.task_id ?? null,
    department: null,
  }
}

export async function listActivities(
  params?: ActivityFilterParams,
): Promise<PaginatedResult<ActivityItem>> {
  const response = await apiClient.get<PaginatedResponse<ActivityEvent>>('/activities', { params })
  const result = unwrapPaginated<ActivityEvent>(response)
  return { ...result, data: result.data.map(mapActivityEventToItem) }
}
