import { apiClient, unwrap, unwrapPaginated, type PaginatedResult } from '../client'
import type { ApiResponse, PaginatedResponse, PaginationParams } from '../types/http'
import type { HealthReport } from '../types/integrations'

export async function listIntegrationHealth(
  params?: PaginationParams,
): Promise<PaginatedResult<HealthReport>> {
  const response = await apiClient.get<PaginatedResponse<HealthReport>>(
    '/integrations/health',
    { params },
  )
  return unwrapPaginated<HealthReport>(response)
}

export async function getSingleIntegrationHealth(
  connectionName: string,
): Promise<HealthReport> {
  const response = await apiClient.get<ApiResponse<HealthReport>>(
    `/integrations/health/${encodeURIComponent(connectionName)}`,
  )
  return unwrap(response)
}
