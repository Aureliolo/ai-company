import { apiClient, unwrap, unwrapVoid } from '../client'
import type { ApiResponse, HumanRole, OrgRole } from '../types'

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

export interface GrantOrgRoleRequest {
  role: OrgRole
  scoped_departments?: readonly string[]
}

export async function listUsers(): Promise<readonly UserResponse[]> {
  const response = await apiClient.get<ApiResponse<readonly UserResponse[]>>('/users')
  return unwrap(response)
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
