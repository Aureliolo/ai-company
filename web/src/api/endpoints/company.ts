import { apiClient, unwrap, unwrapPaginated, unwrapVoid, type PaginatedResult } from '../client'
import type {
  AgentConfig,
  ApiResponse,
  CompanyConfig,
  CreateAgentOrgRequest,
  CreateDepartmentRequest,
  Department,
  DepartmentHealth,
  PaginatedResponse,
  PaginationParams,
  ReorderAgentsRequest,
  ReorderDepartmentsRequest,
  UpdateAgentOrgRequest,
  UpdateCompanyRequest,
  UpdateDepartmentRequest,
} from '../types'

export async function getCompanyConfig(): Promise<CompanyConfig> {
  const response = await apiClient.get<ApiResponse<CompanyConfig>>('/company')
  return unwrap(response)
}

export async function listDepartments(params?: PaginationParams): Promise<PaginatedResult<Department>> {
  const response = await apiClient.get<PaginatedResponse<Department>>('/departments', { params })
  return unwrapPaginated<Department>(response)
}

export async function getDepartment(name: string): Promise<Department> {
  const response = await apiClient.get<ApiResponse<Department>>(`/departments/${encodeURIComponent(name)}`)
  return unwrap(response)
}

export async function getDepartmentHealth(name: string): Promise<DepartmentHealth> {
  const response = await apiClient.get<ApiResponse<DepartmentHealth>>(
    `/departments/${encodeURIComponent(name)}/health`,
  )
  return unwrap(response)
}

// ── Mutation stubs (backend endpoints not yet implemented) ───

export async function updateCompany(data: UpdateCompanyRequest): Promise<CompanyConfig> {
  const response = await apiClient.patch<ApiResponse<CompanyConfig>>('/company', data)
  return unwrap(response)
}

export async function createDepartment(data: CreateDepartmentRequest): Promise<Department> {
  const response = await apiClient.post<ApiResponse<Department>>('/departments', data)
  return unwrap(response)
}

export async function updateDepartment(name: string, data: UpdateDepartmentRequest): Promise<Department> {
  const response = await apiClient.patch<ApiResponse<Department>>(
    `/departments/${encodeURIComponent(name)}`,
    data,
  )
  return unwrap(response)
}

export async function deleteDepartment(name: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(
    `/departments/${encodeURIComponent(name)}`,
  )
  unwrapVoid(response)
}

export async function reorderDepartments(data: ReorderDepartmentsRequest): Promise<CompanyConfig> {
  const response = await apiClient.post<ApiResponse<CompanyConfig>>(
    '/company/reorder-departments',
    data,
  )
  return unwrap(response)
}

export async function createAgentOrg(data: CreateAgentOrgRequest): Promise<AgentConfig> {
  const response = await apiClient.post<ApiResponse<AgentConfig>>('/agents', data)
  return unwrap(response)
}

export async function updateAgentOrg(name: string, data: UpdateAgentOrgRequest): Promise<AgentConfig> {
  const response = await apiClient.patch<ApiResponse<AgentConfig>>(
    `/agents/${encodeURIComponent(name)}`,
    data,
  )
  return unwrap(response)
}

export async function deleteAgent(name: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(
    `/agents/${encodeURIComponent(name)}`,
  )
  unwrapVoid(response)
}

export async function reorderAgents(departmentName: string, data: ReorderAgentsRequest): Promise<Department> {
  const response = await apiClient.post<ApiResponse<Department>>(
    `/departments/${encodeURIComponent(departmentName)}/reorder-agents`,
    data,
  )
  return unwrap(response)
}
