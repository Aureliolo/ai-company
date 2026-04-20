import { apiClient, unwrap } from '../client'
import type { ApiResponse } from '../types/http'
import type { HealthReport } from '../types/integrations'

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
