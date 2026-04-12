import { apiClient, unwrap } from '../client'
import type { ApiResponse, HealthReport } from '../types'

export async function listIntegrationHealth(): Promise<readonly HealthReport[]> {
  const response = await apiClient.get<ApiResponse<readonly HealthReport[]>>(
    '/integrations/health',
  )
  return unwrap(response)
}

export async function getSingleIntegrationHealth(
  connectionName: string,
): Promise<HealthReport> {
  const response = await apiClient.get<ApiResponse<HealthReport>>(
    `/integrations/health/${encodeURIComponent(connectionName)}`,
  )
  return unwrap(response)
}
