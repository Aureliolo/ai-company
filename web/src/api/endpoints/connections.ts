import { apiClient, unwrap, unwrapVoid } from '../client'
import type {
  ApiResponse,
  Connection,
  CreateConnectionRequest,
  HealthReport,
  RevealSecretResponse,
  UpdateConnectionRequest,
} from '../types'

export async function listConnections(): Promise<readonly Connection[]> {
  const response = await apiClient.get<ApiResponse<readonly Connection[]>>('/connections')
  return unwrap(response)
}

export async function getConnection(name: string): Promise<Connection> {
  const response = await apiClient.get<ApiResponse<Connection>>(
    `/connections/${encodeURIComponent(name)}`,
  )
  return unwrap(response)
}

export async function createConnection(
  data: CreateConnectionRequest,
): Promise<Connection> {
  const response = await apiClient.post<ApiResponse<Connection>>('/connections', data)
  return unwrap(response)
}

export async function updateConnection(
  name: string,
  data: UpdateConnectionRequest,
): Promise<Connection> {
  const response = await apiClient.patch<ApiResponse<Connection>>(
    `/connections/${encodeURIComponent(name)}`,
    data,
  )
  return unwrap(response)
}

export async function deleteConnection(name: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(
    `/connections/${encodeURIComponent(name)}`,
  )
  unwrapVoid(response)
}

export async function checkConnectionHealth(name: string): Promise<HealthReport> {
  const response = await apiClient.get<ApiResponse<HealthReport>>(
    `/connections/${encodeURIComponent(name)}/health`,
  )
  return unwrap(response)
}

export async function revealConnectionSecret(
  name: string,
  field: string,
): Promise<RevealSecretResponse> {
  const response = await apiClient.get<ApiResponse<RevealSecretResponse>>(
    `/connections/${encodeURIComponent(name)}/secrets/${encodeURIComponent(field)}`,
  )
  return unwrap(response)
}
