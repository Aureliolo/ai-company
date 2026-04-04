import { create } from 'zustand'
import * as meetingsApi from '@/api/endpoints/meetings'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import { createLogger } from '@/lib/logger'
import type {
  MeetingFilters,
  MeetingResponse,
  TriggerMeetingRequest,
  WsEvent,
} from '@/api/types'

const log = createLogger('meetings')

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
    if (
      typeof candidate.meeting_id === 'string' &&
      typeof candidate.status === 'string' &&
      typeof candidate.meeting_type_name === 'string' &&
      typeof candidate.protocol_type === 'string' &&
      typeof candidate.token_budget === 'number' &&
      Array.isArray(candidate.contribution_rank) &&
      typeof candidate.token_usage_by_participant === 'object' &&
      candidate.token_usage_by_participant !== null
    ) {
      get().upsertMeeting(candidate as unknown as MeetingResponse)
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
