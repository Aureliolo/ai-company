import { apiClient, unwrap, unwrapPaginated, type PaginatedResult } from '../client'
import type {
  ApprovalFilters,
  ApprovalResponse,
  ApproveRequest,
  CreateApprovalRequest,
  RejectRequest,
} from '../types/approvals'
import type { ApiResponse, PaginatedResponse } from '../types/http'

export async function listApprovals(filters?: ApprovalFilters): Promise<PaginatedResult<ApprovalResponse>> {
  const response = await apiClient.get<PaginatedResponse<ApprovalResponse>>('/approvals', { params: filters })
  return unwrapPaginated<ApprovalResponse>(response)
}

export async function getApproval(id: string): Promise<ApprovalResponse> {
  const response = await apiClient.get<ApiResponse<ApprovalResponse>>(`/approvals/${encodeURIComponent(id)}`)
  return unwrap(response)
}

export async function createApproval(data: CreateApprovalRequest): Promise<ApprovalResponse> {
  const response = await apiClient.post<ApiResponse<ApprovalResponse>>('/approvals', data)
  return unwrap(response)
}

export async function approveApproval(id: string, data?: ApproveRequest): Promise<ApprovalResponse> {
  const response = await apiClient.post<ApiResponse<ApprovalResponse>>(`/approvals/${encodeURIComponent(id)}/approve`, data ?? {})
  return unwrap(response)
}

export async function rejectApproval(id: string, data: RejectRequest): Promise<ApprovalResponse> {
  const response = await apiClient.post<ApiResponse<ApprovalResponse>>(`/approvals/${encodeURIComponent(id)}/reject`, data)
  return unwrap(response)
}
