import { apiClient, unwrap, unwrapPaginated, type PaginatedResult } from '../client'
import type { ApiResponse, Channel, Message, PaginatedResponse, PaginationParams } from '../types'

export async function listMessages(params?: PaginationParams & { channel?: string }): Promise<PaginatedResult<Message>> {
  const response = await apiClient.get<PaginatedResponse<Message>>('/messages', { params })
  return unwrapPaginated<Message>(response)
}

export async function listChannels(): Promise<Channel[]> {
  const response = await apiClient.get<ApiResponse<Channel[]>>('/messages/channels')
  return unwrap(response)
}
