import { apiClient, unwrapPaginated, type PaginatedResult } from '../client'
import type { PaginatedResponse, PaginationParams } from '../types'

// TODO: define Artifact interface in types.ts when backend DTO stabilizes
export async function listArtifacts(params?: PaginationParams): Promise<PaginatedResult<Record<string, unknown>>> {
  const response = await apiClient.get<PaginatedResponse<Record<string, unknown>>>('/artifacts', { params })
  return unwrapPaginated<Record<string, unknown>>(response)
}
