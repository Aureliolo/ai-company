import { apiClient, unwrap } from '../client'
import type { ApiResponse } from '../types/http'
import type { HealthStatus } from '../types/system'

export async function getHealth(): Promise<HealthStatus> {
  const response = await apiClient.get<ApiResponse<HealthStatus>>('/health')
  return unwrap(response)
}
