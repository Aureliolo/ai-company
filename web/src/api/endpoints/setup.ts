import { apiClient, unwrap } from '../client'
import type {
  ApiResponse,
  AvailableLocalesResponse,
  SetupAgentRequest,
  SetupAgentResponse,
  SetupAgentSummary,
  SetupAgentsListResponse,
  SetupCompanyRequest,
  SetupCompanyResponse,
  SetupNameLocalesRequest,
  SetupNameLocalesResponse,
  SetupStatusResponse,
  TemplateInfoResponse,
  UpdateAgentModelRequest,
  UpdateAgentNameRequest,
} from '../types'

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

export async function getAgents(): Promise<readonly SetupAgentSummary[]> {
  const response = await apiClient.get<ApiResponse<SetupAgentsListResponse>>('/setup/agents')
  return unwrap(response).agents
}

export async function updateAgentModel(
  index: number,
  data: UpdateAgentModelRequest,
): Promise<SetupAgentSummary> {
  if (!Number.isInteger(index) || index < 0) {
    throw new Error(`Invalid agent index: ${index}`)
  }
  const response = await apiClient.put<ApiResponse<SetupAgentSummary>>(
    `/setup/agents/${index}/model`,
    data,
  )
  return unwrap(response)
}

export async function updateAgentName(
  index: number,
  data: UpdateAgentNameRequest,
): Promise<SetupAgentSummary> {
  if (!Number.isInteger(index) || index < 0) {
    throw new Error(`Invalid agent index: ${index}`)
  }
  const response = await apiClient.put<ApiResponse<SetupAgentSummary>>(
    `/setup/agents/${index}/name`,
    data,
  )
  return unwrap(response)
}

export async function randomizeAgentName(
  index: number,
): Promise<SetupAgentSummary> {
  if (!Number.isInteger(index) || index < 0) {
    throw new Error(`Invalid agent index: ${index}`)
  }
  const response = await apiClient.post<ApiResponse<SetupAgentSummary>>(
    `/setup/agents/${index}/randomize-name`,
  )
  return unwrap(response)
}

export async function getAvailableLocales(): Promise<AvailableLocalesResponse> {
  const response = await apiClient.get<ApiResponse<AvailableLocalesResponse>>('/setup/name-locales/available')
  return unwrap(response)
}

export async function getNameLocales(): Promise<SetupNameLocalesResponse> {
  const response = await apiClient.get<ApiResponse<SetupNameLocalesResponse>>('/setup/name-locales')
  return unwrap(response)
}

export async function saveNameLocales(data: SetupNameLocalesRequest): Promise<SetupNameLocalesResponse> {
  const response = await apiClient.put<ApiResponse<SetupNameLocalesResponse>>('/setup/name-locales', data)
  return unwrap(response)
}

export async function completeSetup(): Promise<{ setup_complete: boolean }> {
  const response = await apiClient.post<ApiResponse<{ setup_complete: boolean }>>('/setup/complete')
  return unwrap(response)
}
