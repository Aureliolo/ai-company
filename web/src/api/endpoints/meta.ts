/**
 * Meta improvement API endpoints.
 *
 * Provides access to improvement proposals, signal domains,
 * A/B tests, configuration, and Chief of Staff chat.
 */

import type { ApiResponse } from '../types/http'
import { apiClient, unwrap } from '../client'

// -- Types -------------------------------------------------------------------

export interface ProposalSummary {
  id: string
  title: string
  action_type: string
  status: string
  risk_level: string
  requested_by: string
  created_at: string
}

export interface SignalDomain {
  name: string
  status: string
}

export interface SignalsResponse {
  enabled: boolean
  domains: SignalDomain[]
}

export interface ABTestGroupMetrics {
  group: 'control' | 'treatment'
  agent_count: number
  observation_count: number
  avg_quality_score: number
  avg_success_rate: number
  total_spend: number
}

export interface ABTestSummary {
  proposal_id: string
  proposal_title: string
  control_metrics: ABTestGroupMetrics
  treatment_metrics: ABTestGroupMetrics
  verdict:
    | 'treatment_wins'
    | 'control_wins'
    | 'inconclusive'
    | 'treatment_regressed'
    | null
  observation_hours_elapsed: number
  observation_hours_total: number
}

export interface MetaConfig {
  enabled: boolean
  chief_of_staff_enabled: boolean
  config_tuning_enabled: boolean
  architecture_proposals_enabled: boolean
  prompt_tuning_enabled: boolean
  code_modification_enabled: boolean
}

export interface ChatResponse {
  answer: string
  sources: string[]
  confidence: number
}

// -- API functions -----------------------------------------------------------

const BASE = '/meta'

export async function getMetaConfig(): Promise<MetaConfig> {
  const response =
    await apiClient.get<ApiResponse<MetaConfig>>(`${BASE}/config`)
  return unwrap(response)
}

export async function listProposals(): Promise<ProposalSummary[]> {
  const response = await apiClient.get<ApiResponse<ProposalSummary[]>>(
    `${BASE}/proposals`,
  )
  return unwrap(response)
}

export async function getSignals(): Promise<SignalsResponse> {
  const response = await apiClient.get<ApiResponse<SignalsResponse>>(
    `${BASE}/signals`,
  )
  return unwrap(response)
}

export async function listABTests(): Promise<ABTestSummary[]> {
  const response = await apiClient.get<ApiResponse<ABTestSummary[]>>(
    `${BASE}/ab-tests`,
  )
  return unwrap(response)
}

export async function postChat(question: string): Promise<ChatResponse> {
  const trimmed = question.trim()
  if (!trimmed) {
    throw new Error('Question must not be blank')
  }
  const response = await apiClient.post<ApiResponse<ChatResponse>>(
    `${BASE}/chat`,
    { question: trimmed },
  )
  return unwrap(response)
}
