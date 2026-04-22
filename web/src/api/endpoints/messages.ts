import { apiClient, unwrapPaginated, type PaginatedResult } from '../client'
import type { PaginatedResponse, PaginationParams } from '../types/http'
import type { Channel, Message } from '../types/messages'

export async function listMessages(params?: PaginationParams & { channel?: string; signal?: AbortSignal }): Promise<PaginatedResult<Message>> {
  const { signal, ...queryParams } = params ?? {}
  const response = await apiClient.get<PaginatedResponse<Message>>('/messages', { params: queryParams, signal })
  return unwrapPaginated<Message>(response)
}

export async function listChannels(
  params?: PaginationParams & { signal?: AbortSignal },
): Promise<PaginatedResult<Channel>> {
  const { signal, ...queryParams } = params ?? {}
  const response = await apiClient.get<PaginatedResponse<Channel>>(
    '/messages/channels',
    { params: queryParams, signal },
  )
  return unwrapPaginated<Channel>(response)
}
