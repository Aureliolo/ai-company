/** Response envelopes and pagination helpers. */

import type { ErrorDetail } from './errors'

/** Discriminated API response envelope. */
export type ApiResponse<T> =
  | { data: T; error: null; error_detail: null; success: true }
  | { data: null; error: string | null; error_detail: ErrorDetail | null; success: false }

export interface PaginationMeta {
  total: number
  offset: number
  limit: number
}

/** Discriminated paginated response envelope. */
export type PaginatedResponse<T> =
  | { data: T[]; error: null; error_detail: null; success: true; pagination: PaginationMeta; degraded_sources?: readonly string[] }
  | { data: null; error: string | null; error_detail: ErrorDetail | null; success: false; pagination: null; degraded_sources?: readonly string[] }

export interface PaginationParams {
  offset?: number
  limit?: number
}
