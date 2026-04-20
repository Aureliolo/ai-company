import { apiClient, unwrap } from '../client'
import type { ApiResponse } from '../types/http'
import type {
  OauthInitiateRequest,
  OauthInitiateResponse,
  OauthTokenStatus,
} from '../types/integrations'

export async function initiateOauth(
  data: OauthInitiateRequest,
): Promise<OauthInitiateResponse> {
  const response = await apiClient.post<ApiResponse<OauthInitiateResponse>>(
    '/oauth/initiate',
    data,
  )
  return unwrap(response)
}

export async function getOauthStatus(
  connectionName: string,
): Promise<OauthTokenStatus> {
  const response = await apiClient.get<ApiResponse<OauthTokenStatus>>(
    `/oauth/status/${encodeURIComponent(connectionName)}`,
  )
  return unwrap(response)
}
