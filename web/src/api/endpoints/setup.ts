import { apiClient, unwrap } from '../client'
import type {
  ApiResponse,
  SetupAgentRequest,
  SetupAgentResponse,
  SetupCompanyRequest,
  SetupCompanyResponse,
  SetupStatusResponse,
  TemplateInfoResponse,
} from '../types'

// Note: getSetupStatus doesn't need auth -- the endpoint is public.
// apiClient already handles missing auth tokens gracefully (no header sent).
export async function getSetupStatus(): Promise<SetupStatusResponse> {
  const response = await apiClient.get<ApiResponse<SetupStatusResponse>>('/setup/status')
  return unwrap(response)
}

export async function listTemplates(): Promise<TemplateInfoResponse[]> {
  const response = await apiClient.get<ApiResponse<TemplateInfoResponse[]>>('/setup/templates')
  return unwrap(response)
}

export async function createCompany(data: SetupCompanyRequest): Promise<SetupCompanyResponse> {
  const response = await apiClient.post<ApiResponse<SetupCompanyResponse>>('/setup/company', data)
  return unwrap(response)
}

export async function createAgent(data: SetupAgentRequest): Promise<SetupAgentResponse> {
  const response = await apiClient.post<ApiResponse<SetupAgentResponse>>('/setup/agent', data)
  return unwrap(response)
}

export async function completeSetup(): Promise<{ setup_complete: boolean }> {
  const response = await apiClient.post<ApiResponse<{ setup_complete: boolean }>>('/setup/complete')
  return unwrap(response)
}
