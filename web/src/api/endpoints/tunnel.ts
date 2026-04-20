import { apiClient, unwrap, unwrapVoid } from '../client'
import type { ApiResponse } from '../types/http'
import type { TunnelStatus } from '../types/integrations'

export async function getTunnelStatus(): Promise<TunnelStatus> {
  const response = await apiClient.get<ApiResponse<TunnelStatus>>(
    '/integrations/tunnel/status',
  )
  return unwrap(response)
}

export async function startTunnel(): Promise<{ public_url: string }> {
  const response = await apiClient.post<ApiResponse<{ public_url: string }>>(
    '/integrations/tunnel/start',
  )
  return unwrap(response)
}

export async function stopTunnel(): Promise<void> {
  const response = await apiClient.post<ApiResponse<null>>(
    '/integrations/tunnel/stop',
  )
  unwrapVoid(response)
}
