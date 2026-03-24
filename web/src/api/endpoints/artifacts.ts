import { apiClient, unwrapPaginated } from '../client'
import type { PaginatedResponse, PaginationParams } from '../types'

export async function listArtifacts(params?: PaginationParams) {
  const response = await apiClient.get<PaginatedResponse<Record<string, unknown>>>('/artifacts', { params })
  return unwrapPaginated<Record<string, unknown>>(response)
}
