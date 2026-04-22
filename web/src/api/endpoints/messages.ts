import { apiClient, unwrapPaginated, type PaginatedResult } from '../client'
import type { PaginatedResponse, PaginationParams } from '../types/http'
import type { Channel, Message } from '../types/messages'

export async function listMessages(params?: PaginationParams & { channel?: string; signal?: AbortSignal }): Promise<PaginatedResult<Message>> {
  const { signal, ...queryParams } = params ?? {}
  const response = await apiClient.get<PaginatedResponse<Message>>('/messages', { params: queryParams, signal })
  return unwrapPaginated<Message>(response)
}

export async function listChannels(
  params?: { cursor?: string | null; limit?: number },
): Promise<PaginatedResult<Channel>> {
  const response = await apiClient.get<PaginatedResponse<Channel>>(
    '/messages/channels',
    { params },
  )
  return unwrapPaginated<Channel>(response)
}
