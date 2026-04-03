import { apiClient, unwrap, unwrapPaginated, unwrapVoid, type PaginatedResult } from '../client'
import type {
  ApiResponse,
  CreateWorkflowDefinitionRequest,
  PaginatedResponse,
  UpdateWorkflowDefinitionRequest,
  WorkflowDefinition,
  WorkflowValidationResult,
} from '../types'

export async function listWorkflows(filters?: {
  workflow_type?: string
  offset?: number
  limit?: number
}): Promise<PaginatedResult<WorkflowDefinition>> {
  const response = await apiClient.get<PaginatedResponse<WorkflowDefinition>>(
    '/workflows',
    { params: filters },
  )
  return unwrapPaginated<WorkflowDefinition>(response)
}

export async function getWorkflow(id: string): Promise<WorkflowDefinition> {
  const response = await apiClient.get<ApiResponse<WorkflowDefinition>>(
    `/workflows/${encodeURIComponent(id)}`,
  )
  return unwrap(response)
}

export async function createWorkflow(
  data: CreateWorkflowDefinitionRequest,
): Promise<WorkflowDefinition> {
  const response = await apiClient.post<ApiResponse<WorkflowDefinition>>(
    '/workflows',
    data,
  )
  return unwrap(response)
}

export async function updateWorkflow(
  id: string,
  data: UpdateWorkflowDefinitionRequest,
): Promise<WorkflowDefinition> {
  const response = await apiClient.patch<ApiResponse<WorkflowDefinition>>(
    `/workflows/${encodeURIComponent(id)}`,
    data,
  )
  return unwrap(response)
}

export async function deleteWorkflow(id: string): Promise<void> {
  const response = await apiClient.delete(`/workflows/${encodeURIComponent(id)}`)
  unwrapVoid(response)
}

export async function validateWorkflow(id: string): Promise<WorkflowValidationResult> {
  const response = await apiClient.post<ApiResponse<WorkflowValidationResult>>(
    `/workflows/${encodeURIComponent(id)}/validate`,
  )
  return unwrap(response)
}

export async function validateWorkflowDraft(
  data: CreateWorkflowDefinitionRequest,
): Promise<WorkflowValidationResult> {
  const response = await apiClient.post<ApiResponse<WorkflowValidationResult>>(
    '/workflows/validate-draft',
    data,
  )
  return unwrap(response)
}

export async function exportWorkflowYaml(id: string): Promise<string> {
  const response = await apiClient.post<string>(
    `/workflows/${encodeURIComponent(id)}/export`,
    undefined,
    { responseType: 'text' },
  )
  return response.data
}
