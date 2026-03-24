import { apiClient, unwrap } from '../client'
import type { ApiResponse, CoordinateTaskRequest, CoordinationResultResponse } from '../types'

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
