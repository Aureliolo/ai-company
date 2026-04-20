/** Meeting protocol, agenda, contribution and minutes types. */

import type { Priority } from './enums'

export type MeetingStatus =
  | 'scheduled'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'budget_exhausted'

export const MEETING_STATUS_VALUES = [
  'scheduled', 'in_progress', 'completed', 'failed', 'cancelled', 'budget_exhausted',
] as const satisfies readonly MeetingStatus[]

export type MeetingProtocolType =
  | 'round_robin'
  | 'position_papers'
  | 'structured_phases'

export interface MeetingAgendaItem {
  title: string
  description: string
  presenter_id: string | null
}

export interface MeetingAgenda {
  title: string
  context: string
  readonly items: readonly MeetingAgendaItem[]
}

export type MeetingPhase =
  | 'agenda_broadcast'
  | 'round_robin_turn'
  | 'position_paper'
  | 'input_gathering'
  | 'discussion'
  | 'synthesis'
  | 'summary'

export interface MeetingContribution {
  agent_id: string
  content: string
  phase: MeetingPhase
  turn_number: number
  input_tokens: number
  output_tokens: number
  timestamp: string
}

export interface ActionItem {
  description: string
  assignee_id: string | null
  priority: Priority
}

export interface MeetingMinutes {
  meeting_id: string
  protocol_type: MeetingProtocolType
  leader_id: string
  readonly participant_ids: readonly string[]
  agenda: MeetingAgenda
  readonly contributions: readonly MeetingContribution[]
  summary: string
  readonly decisions: readonly string[]
  readonly action_items: readonly ActionItem[]
  conflicts_detected: boolean
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  started_at: string
  ended_at: string
}

export interface MeetingRecord {
  meeting_id: string
  meeting_type_name: string
  protocol_type: MeetingProtocolType
  status: MeetingStatus
  minutes: MeetingMinutes | null
  error_message: string | null
  token_budget: number
}

export interface MeetingResponse extends MeetingRecord {
  token_usage_by_participant: Record<string, number>
  contribution_rank: readonly string[]
  meeting_duration_seconds: number | null
}

export interface MeetingFilters {
  status?: MeetingStatus
  meeting_type?: string
  offset?: number
  limit?: number
}

export interface TriggerMeetingRequest {
  event_name: string
  context?: Record<string, string | string[]>
}
