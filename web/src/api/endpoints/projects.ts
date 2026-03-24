import { apiClient, unwrapPaginated } from '../client'
import type { PaginatedResponse, PaginationParams } from '../types'

export async function listProjects(params?: PaginationParams) {
  const response = await apiClient.get<PaginatedResponse<Record<string, unknown>>>('/projects', { params })
  return unwrapPaginated<Record<string, unknown>>(response)
}
