import { apiClient, unwrap, unwrapVoid } from '../client'
import type { OverrideResponse, SetOverrideRequest } from '../types/collaboration'
import type { ApiResponse } from '../types/http'

const basePath = (agentId: string) =>
  `/agents/${encodeURIComponent(agentId)}/quality`

export async function getQualityOverride(agentId: string): Promise<OverrideResponse> {
  const response = await apiClient.get<ApiResponse<OverrideResponse>>(
    `${basePath(agentId)}/override`,
  )
  return unwrap(response)
}

export async function setQualityOverride(
  agentId: string,
  data: SetOverrideRequest,
): Promise<OverrideResponse> {
  const response = await apiClient.post<ApiResponse<OverrideResponse>>(
    `${basePath(agentId)}/override`,
    data,
  )
  return unwrap(response)
}

export async function clearQualityOverride(agentId: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(
    `${basePath(agentId)}/override`,
  )
  unwrapVoid(response)
}
