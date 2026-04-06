import { apiClient, unwrap, unwrapVoid } from '../client'
import type {
  ApiResponse,
  AuthResponse,
  ChangePasswordRequest,
  LoginRequest,
  PaginatedResponse,
  SessionInfo,
  SetupRequest,
  UserInfoResponse,
  WsTicketResponse,
} from '../types'
import { unwrapPaginated, type PaginatedResult } from '../client'

export async function setup(data: SetupRequest): Promise<AuthResponse> {
  const response = await apiClient.post<ApiResponse<AuthResponse>>('/auth/setup', data)
  return unwrap(response)
}

export async function login(data: LoginRequest): Promise<AuthResponse> {
  const response = await apiClient.post<ApiResponse<AuthResponse>>('/auth/login', data)
  return unwrap(response)
}

export async function logout(): Promise<void> {
  const response = await apiClient.post<ApiResponse<null>>('/auth/logout')
  unwrapVoid(response)
}

export async function changePassword(data: ChangePasswordRequest): Promise<UserInfoResponse> {
  const response = await apiClient.post<ApiResponse<UserInfoResponse>>('/auth/change-password', data)
  return unwrap(response)
}

export async function getMe(): Promise<UserInfoResponse> {
  const response = await apiClient.get<ApiResponse<UserInfoResponse>>('/auth/me')
  return unwrap(response)
}

export async function getWsTicket(): Promise<WsTicketResponse> {
  const response = await apiClient.post<ApiResponse<WsTicketResponse>>('/auth/ws-ticket')
  return unwrap(response)
}

export async function listSessions(
  offset = 0,
  limit = 50,
): Promise<PaginatedResult<SessionInfo>> {
  const response = await apiClient.get<PaginatedResponse<SessionInfo>>(
    '/auth/sessions',
    { params: { offset, limit } },
  )
  return unwrapPaginated(response)
}

export async function revokeSession(sessionId: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse<null>>(
    `/auth/sessions/${encodeURIComponent(sessionId)}`,
  )
  unwrapVoid(response)
}
