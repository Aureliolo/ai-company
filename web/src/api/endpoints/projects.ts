import { apiClient, unwrapPaginated, type PaginatedResult } from '../client'
import type { PaginatedResponse, PaginationParams } from '../types'

// TODO: define Project interface in types.ts when backend DTO stabilizes
export async function listProjects(params?: PaginationParams): Promise<PaginatedResult<Record<string, unknown>>> {
  const response = await apiClient.get<PaginatedResponse<Record<string, unknown>>>('/projects', { params })
  return unwrapPaginated<Record<string, unknown>>(response)
}
