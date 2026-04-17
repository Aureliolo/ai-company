/**
 * Human escalation approval queue client (#1418).
 *
 * Operators list pending escalations, inspect the originating conflict,
 * submit a decision (winner or reject), or cancel a stuck escalation.
 * Responses flow through the shared {@link ApiResponse} /
 * {@link PaginatedResponse} envelopes; 429 responses are handled
 * transparently by the shared axios client (see ``api/client.ts``).
 */

import {
  apiClient,
  unwrap,
  unwrapPaginated,
  type PaginatedResult,
} from '../client'
import type {
  ApiResponse,
  CancelEscalationRequest,
  Escalation,
  EscalationResponse,
  EscalationStatus,
  PaginatedResponse,
  SubmitDecisionRequest,
} from '../types'

const BASE = '/conflicts/escalations'

export interface ListEscalationsFilters {
  readonly status?: EscalationStatus
  readonly limit?: number
  readonly offset?: number
}

export async function listEscalations(
  filters?: ListEscalationsFilters,
): Promise<PaginatedResult<EscalationResponse>> {
  const response = await apiClient.get<PaginatedResponse<EscalationResponse>>(
    BASE,
    { params: filters },
  )
  return unwrapPaginated<EscalationResponse>(response)
}

export async function getEscalation(id: string): Promise<EscalationResponse> {
  const response = await apiClient.get<ApiResponse<EscalationResponse>>(
    `${BASE}/${encodeURIComponent(id)}`,
  )
  return unwrap(response)
}

export async function submitEscalationDecision(
  id: string,
  data: SubmitDecisionRequest,
): Promise<Escalation> {
  const response = await apiClient.post<ApiResponse<Escalation>>(
    `${BASE}/${encodeURIComponent(id)}/decision`,
    data,
  )
  return unwrap(response)
}

export async function cancelEscalation(
  id: string,
  data: CancelEscalationRequest,
): Promise<Escalation> {
  const response = await apiClient.post<ApiResponse<Escalation>>(
    `${BASE}/${encodeURIComponent(id)}/cancel`,
    data,
  )
  return unwrap(response)
}
