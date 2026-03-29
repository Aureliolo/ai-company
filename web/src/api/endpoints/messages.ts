import { apiClient, unwrap, unwrapPaginated, type PaginatedResult } from '../client'
import type { ApiResponse, Channel, Message, PaginatedResponse, PaginationParams } from '../types'

export async function listMessages(params?: PaginationParams & { channel?: string; signal?: AbortSignal }): Promise<PaginatedResult<Message>> {
  const { signal, ...queryParams } = params ?? {}
  const response = await apiClient.get<PaginatedResponse<Message>>('/messages', { params: queryParams, signal })
  return unwrapPaginated<Message>(response)
}

export async function listChannels(): Promise<Channel[]> {
  const response = await apiClient.get<ApiResponse<Channel[]>>('/messages/channels')
  return unwrap(response)
}
