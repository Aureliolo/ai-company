import { create } from 'zustand'
import * as meetingsApi from '@/api/endpoints/meetings'
import {
  MEETING_PROTOCOL_TYPE_VALUES,
  MEETING_STATUS_VALUES,
} from '@/api/types/meetings'
import { sanitizeWsString } from '@/stores/notifications'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import { createLogger } from '@/lib/logger'
import type {
  MeetingAgenda,
  MeetingContribution,
  MeetingFilters,
  MeetingMinutes,
  MeetingResponse,
  TriggerMeetingRequest,
} from '@/api/types/meetings'
import type { WsEvent } from '@/api/types/websocket'

const log = createLogger('meetings')

// Runtime sets derived from the canonical enum tuples -- any drift
// between validator and union is caught at compile time.
const MEETING_STATUS_SET: ReadonlySet<string> = new Set<string>(MEETING_STATUS_VALUES)
const MEETING_PROTOCOL_TYPE_SET: ReadonlySet<string> = new Set<string>(MEETING_PROTOCOL_TYPE_VALUES)

/** Validate that a ``token_usage_by_participant`` map is a plain ``Record<string, number>``. */
function isTokenUsageMap(value: unknown): value is Record<string, number> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  for (const [key, count] of Object.entries(value)) {
    if (typeof key !== 'string' || typeof count !== 'number') return false
  }
  return true
}

/**
 * Type predicate: a WS payload object satisfies the {@link MeetingResponse}
 * shape so consumers can use it without a cast. ``contribution_rank``
 * must be a plain string array of agent ids (matching the declared
 * ``readonly string[]``) and ``token_usage_by_participant`` must be a
 * plain ``Record<string, number>`` -- accepting non-string ranks or
 * array-shaped usage maps would let malformed payloads smuggle bad
 * values into the store.
 */
function isMeetingShape(
  c: Record<string, unknown>,
): c is Record<string, unknown> & MeetingResponse {
  return (
    typeof c.meeting_id === 'string' &&
    typeof c.status === 'string' &&
    MEETING_STATUS_SET.has(c.status) &&
    typeof c.meeting_type_name === 'string' &&
    typeof c.protocol_type === 'string' &&
    MEETING_PROTOCOL_TYPE_SET.has(c.protocol_type) &&
    typeof c.token_budget === 'number' &&
    Array.isArray(c.contribution_rank) &&
    c.contribution_rank.every((entry) => typeof entry === 'string') &&
    isTokenUsageMap(c.token_usage_by_participant) &&
    // Remaining non-optional ``MeetingResponse`` fields. ``minutes``
    // and ``error_message`` are nullable on the wire (completed
    // meetings fill in ``minutes``; failed meetings fill in
    // ``error_message``). ``meeting_duration_seconds`` is null while
    // in-progress and becomes a number once ended. Accepting null
    // for all three matches the declared types and keeps the guard
    // aligned with the asserted ``MeetingResponse`` shape.
    (c.minutes === null || (typeof c.minutes === 'object' && !Array.isArray(c.minutes))) &&
    (c.error_message === null || typeof c.error_message === 'string') &&
    (c.meeting_duration_seconds === null ||
      typeof c.meeting_duration_seconds === 'number')
  )
}

/**
 * Return a sanitized copy of a ``MeetingResponse`` with every
 * untrusted string field validated by ``isMeetingShape`` routed
 * through ``sanitizeWsString`` so bidi overrides and control chars
 * never reach the rendered UI. This covers every WS-origin string
 * the store persists: the identifier (``meeting_id``), the enum-
 * typed display strings, the nullable ``error_message``, the
 * ``contribution_rank`` agent ids, and the participant-id keys of
 * ``token_usage_by_participant``.
 */
function sanitizeAgenda(agenda: MeetingAgenda): MeetingAgenda {
  return {
    title: sanitizeWsString(agenda.title, 256) ?? '',
    context: sanitizeWsString(agenda.context, 2048) ?? '',
    items: agenda.items.map((item) => ({
      title: sanitizeWsString(item.title, 256) ?? '',
      description: sanitizeWsString(item.description, 1024) ?? '',
      presenter_id:
        item.presenter_id === null
          ? null
          : sanitizeWsString(item.presenter_id, 128) ?? '',
    })),
  }
}

function sanitizeContribution(c: MeetingContribution): MeetingContribution {
  return {
    ...c,
    agent_id: sanitizeWsString(c.agent_id, 128) ?? '',
    content: sanitizeWsString(c.content, 4096) ?? '',
    timestamp: sanitizeWsString(c.timestamp, 64) ?? '',
  }
}

function sanitizeMeetingMinutes(
  minutes: MeetingMinutes | null,
): MeetingMinutes | null {
  if (minutes === null) return null
  return {
    ...minutes,
    meeting_id: sanitizeWsString(minutes.meeting_id, 128) ?? '',
    protocol_type:
      (sanitizeWsString(minutes.protocol_type, 64) ?? '') as MeetingMinutes['protocol_type'],
    leader_id: sanitizeWsString(minutes.leader_id, 128) ?? '',
    participant_ids: minutes.participant_ids
      .map((id) => sanitizeWsString(id, 128) ?? '')
      .filter((id) => id.length > 0),
    agenda: sanitizeAgenda(minutes.agenda),
    contributions: minutes.contributions.map(sanitizeContribution),
    summary: sanitizeWsString(minutes.summary, 4096) ?? '',
    decisions: minutes.decisions
      .map((d) => sanitizeWsString(d, 1024) ?? '')
      .filter((d) => d.length > 0),
    action_items: minutes.action_items.map((ai) => ({
      description: sanitizeWsString(ai.description, 1024) ?? '',
      assignee_id:
        ai.assignee_id === null
          ? null
          : sanitizeWsString(ai.assignee_id, 128) ?? '',
      priority: ai.priority,
    })),
    started_at: sanitizeWsString(minutes.started_at, 64) ?? '',
    ended_at: sanitizeWsString(minutes.ended_at, 64) ?? '',
  }
}

function sanitizeMeeting(c: MeetingResponse): MeetingResponse {
  const tokenUsage: Record<string, number> = {}
  for (const [participantId, count] of Object.entries(c.token_usage_by_participant)) {
    const safeId = sanitizeWsString(participantId, 128)
    if (safeId && safeId.length > 0) {
      tokenUsage[safeId] = count
    }
  }
  return {
    ...c,
    meeting_id: sanitizeWsString(c.meeting_id, 128) ?? '',
    meeting_type_name: sanitizeWsString(c.meeting_type_name, 128) ?? '',
    status: (sanitizeWsString(c.status, 64) ?? '') as MeetingResponse['status'],
    protocol_type: (sanitizeWsString(c.protocol_type, 64) ?? '') as MeetingResponse['protocol_type'],
    error_message:
      c.error_message === null ? null : sanitizeWsString(c.error_message, 512) ?? '',
    minutes: sanitizeMeetingMinutes(c.minutes),
    token_usage_by_participant: tokenUsage,
    contribution_rank: c.contribution_rank
      .map((agentId) => sanitizeWsString(agentId, 128) ?? '')
      .filter((agentId) => agentId.length > 0),
  }
}

export interface MeetingsState {
  // Data
  meetings: MeetingResponse[]
  selectedMeeting: MeetingResponse | null
  total: number

  // Loading
  loading: boolean
  loadingDetail: boolean
  error: string | null
  detailError: string | null

  // Trigger
  triggering: boolean

  // Actions
  fetchMeetings: (filters?: MeetingFilters) => Promise<void>
  fetchMeeting: (meetingId: string) => Promise<void>
  triggerMeeting: (data: TriggerMeetingRequest) => Promise<MeetingResponse[]>

  // Real-time
  handleWsEvent: (event: WsEvent) => void
  upsertMeeting: (meeting: MeetingResponse) => void
}

let listRequestSeq = 0
let detailRequestSeq = 0

/** Reset module-level request seq counters -- test-only. */
export function _resetRequestSeqs(): void {
  listRequestSeq = 0
  detailRequestSeq = 0
}

export const useMeetingsStore = create<MeetingsState>()((set, get) => ({
  meetings: [],
  selectedMeeting: null,
  total: 0,
  loading: false,
  loadingDetail: false,
  error: null,
  detailError: null,
  triggering: false,

  fetchMeetings: async (filters) => {
    const seq = ++listRequestSeq
    set({ loading: true, error: null })
    try {
      const result = await meetingsApi.listMeetings(filters)
      if (seq !== listRequestSeq) return // stale response
      // Sync selectedMeeting with fresh data
      const currentSelected = get().selectedMeeting
      const freshSelected = currentSelected
        ? result.data.find((m) => m.meeting_id === currentSelected.meeting_id) ?? currentSelected
        : null
      set({
        meetings: result.data,
        total: result.total,
        loading: false,
        selectedMeeting: freshSelected,
      })
    } catch (err) {
      if (seq !== listRequestSeq) {
        log.warn('Discarding error from stale list request:', getErrorMessage(err))
        return
      }
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  fetchMeeting: async (meetingId) => {
    const seq = ++detailRequestSeq
    const current = get().selectedMeeting
    set({
      loadingDetail: true,
      detailError: null,
      selectedMeeting: current?.meeting_id === meetingId ? current : null,
    })
    try {
      const meeting = await meetingsApi.getMeeting(meetingId)
      if (seq !== detailRequestSeq) return // stale response
      set({ selectedMeeting: meeting, loadingDetail: false, detailError: null })
    } catch (err) {
      if (seq !== detailRequestSeq) {
        log.warn('Discarding error from stale detail request:', getErrorMessage(err))
        return
      }
      set({ loadingDetail: false, detailError: getErrorMessage(err) })
    }
  },

  triggerMeeting: async (data) => {
    set({ triggering: true })
    try {
      const meetings = await meetingsApi.triggerMeeting(data)
      set((s) => ({
        triggering: false,
        meetings: [...meetings, ...s.meetings],
        total: s.total + meetings.length,
      }))
      return meetings
    } catch (err) {
      log.error('triggerMeeting failed:', getErrorMessage(err))
      set({ triggering: false })
      throw err
    }
  },

  handleWsEvent: (event) => {
    const { payload } = event
    if (!payload.meeting || typeof payload.meeting !== 'object' || Array.isArray(payload.meeting)) {
      log.warn('Event has no meeting payload, skipping:', event.event_type)
      return
    }
    const candidate = payload.meeting as Record<string, unknown>
    if (isMeetingShape(candidate)) {
      const sanitized = sanitizeMeeting(candidate)
      if (!sanitized.meeting_id) {
        // sanitizeWsString can return '' for a whitespace-only or
        // all-control-char id that isMeetingShape accepted as a
        // string. Upserting under '' would collapse unrelated meetings
        // into the same slot -- skip and log instead.
        log.error(
          'Meeting payload has empty id after sanitization, skipping upsert',
          { meeting_id: sanitizeForLog(candidate.meeting_id) },
        )
        return
      }
      get().upsertMeeting(sanitized)
    } else {
      log.error('Received malformed meeting WS payload, skipping upsert', {
        meeting_id: sanitizeForLog(candidate.meeting_id),
        hasStatus: typeof candidate.status === 'string',
        hasTypeName: typeof candidate.meeting_type_name === 'string',
        hasTokenBudget: typeof candidate.token_budget === 'number',
      })
    }
  },

  upsertMeeting: (meeting) => {
    set((s) => {
      const idx = s.meetings.findIndex((m) => m.meeting_id === meeting.meeting_id)
      const newMeetings = idx === -1
        ? [meeting, ...s.meetings]
        : s.meetings.map((m, i) => (i === idx ? meeting : m))
      const selectedMeeting = s.selectedMeeting?.meeting_id === meeting.meeting_id
        ? meeting
        : s.selectedMeeting
      return {
        meetings: newMeetings,
        selectedMeeting,
        ...(idx === -1 ? { total: s.total + 1 } : {}),
      }
    })
  },
}))
