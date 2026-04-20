/** Authentication and session types. */

import type { HumanRole, OrgRole } from './enums'

export interface CredentialsRequest {
  username: string
  password: string
}

/** Alias for setup endpoint. */
export type SetupRequest = CredentialsRequest

/** Alias for login endpoint. */
export type LoginRequest = CredentialsRequest

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

/** @deprecated Use {@link AuthResponse} -- backend no longer returns token in body. */
export interface TokenResponse {
  token: string
  expires_in: number
  must_change_password: boolean
}

/** Cookie-based auth response (no token in body -- JWT is in HttpOnly cookie). */
export interface AuthResponse {
  expires_in: number
  must_change_password: boolean
}

/** Active session metadata returned by the session management API. */
export interface SessionInfo {
  session_id: string
  user_id: string
  username: string
  ip_address: string
  user_agent: string
  created_at: string
  last_active_at: string
  expires_at: string
  is_current: boolean
}

export interface WsTicketResponse {
  ticket: string
  expires_in: number
}

export interface UserInfoResponse {
  id: string
  username: string
  role: HumanRole
  must_change_password: boolean
  org_roles: readonly OrgRole[]
  scoped_departments: readonly string[]
}
