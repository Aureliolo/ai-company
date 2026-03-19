import { apiClient, unwrap } from '../client'
import type {
  ApiResponse,
  SetupAgentRequest,
  SetupCompanyRequest,
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

export async function createCompany(data: SetupCompanyRequest): Promise<{ company_name: string; template_applied: string | null; department_count: number }> {
  const response = await apiClient.post<ApiResponse<{ company_name: string; template_applied: string | null; department_count: number }>>('/setup/company', data)
  return unwrap(response)
}

export async function createAgent(data: SetupAgentRequest): Promise<{ name: string; role: string; department: string; model_provider: string; model_id: string }> {
  const response = await apiClient.post<ApiResponse<{ name: string; role: string; department: string; model_provider: string; model_id: string }>>('/setup/agent', data)
  return unwrap(response)
}

export async function completeSetup(): Promise<{ setup_complete: boolean }> {
  const response = await apiClient.post<ApiResponse<{ setup_complete: boolean }>>('/setup/complete')
  return unwrap(response)
}
