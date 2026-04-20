import { apiClient, unwrap } from '../client'
import type { CoordinateTaskRequest, CoordinationResultResponse } from '../types/coordination'
import type { ApiResponse } from '../types/http'

export async function coordinateTask(
  taskId: string,
  data?: CoordinateTaskRequest,
): Promise<CoordinationResultResponse> {
  const response = await apiClient.post<ApiResponse<CoordinationResultResponse>>(
    `/tasks/${encodeURIComponent(taskId)}/coordinate`,
    data ?? {},
  )
  return unwrap(response)
}
