import { apiClient, unwrap, unwrapPaginated, unwrapVoid, type PaginatedResult } from '../client'
import type { HumanRole, OrgRole } from '../types/enums'
import type { ApiResponse, PaginatedResponse, PaginationParams } from '../types/http'

export interface UserResponse {
  id: string
  username: string
  role: HumanRole
  must_change_password: boolean
  org_roles: readonly OrgRole[]
  scoped_departments: readonly string[]
  created_at: string
  updated_at: string
}

export type GrantOrgRoleRequest =
  | { role: 'department_admin'; scoped_departments: readonly string[] }
  | { role: Exclude<OrgRole, 'department_admin'>; scoped_departments?: never }

export async function listUsers(
  params?: PaginationParams,
): Promise<PaginatedResult<UserResponse>> {
  const response = await apiClient.get<PaginatedResponse<UserResponse>>('/users', { params })
  return unwrapPaginated<UserResponse>(response)
}

export async function grantOrgRole(userId: string, data: GrantOrgRoleRequest): Promise<UserResponse> {
  const response = await apiClient.post<ApiResponse<UserResponse>>(
    `/users/${encodeURIComponent(userId)}/org-roles`,
    data,
  )
  return unwrap(response)
}

export async function revokeOrgRole(userId: string, role: OrgRole): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(
    `/users/${encodeURIComponent(userId)}/org-roles/${encodeURIComponent(role)}`,
  )
  unwrapVoid(response)
}
