import { http, HttpResponse } from 'msw'
import type {
  getMeeting,
  listMeetings,
  triggerMeeting,
} from '@/api/endpoints/meetings'
import type { MeetingResponse } from '@/api/types'
import { apiError, emptyPage, paginatedFor, successFor } from './helpers'

export function buildMeeting(
  overrides: Partial<MeetingResponse> = {},
): MeetingResponse {
  return {
    meeting_id: 'meeting-default',
    meeting_type_name: 'default_meeting',
    protocol_type: 'round_robin',
    status: 'scheduled',
    minutes: null,
    error_message: null,
    token_budget: 10_000,
    token_usage_by_participant: {},
    contribution_rank: [],
    meeting_duration_seconds: null,
    ...overrides,
  }
}

export const meetingsHandlers = [
  http.get('/api/v1/meetings', () =>
    HttpResponse.json(paginatedFor<typeof listMeetings>(emptyPage())),
  ),
  http.get('/api/v1/meetings/:id', ({ params }) =>
    HttpResponse.json(
      successFor<typeof getMeeting>(
        buildMeeting({ meeting_id: String(params.id) }),
      ),
    ),
  ),
  http.post('/api/v1/meetings/trigger', async ({ request }) => {
    let body: unknown
    try {
      body = await request.json()
    } catch {
      return HttpResponse.json(apiError("Field 'event_name' is required"), {
        status: 400,
      })
    }
    if (
      !body ||
      typeof body !== 'object' ||
      typeof (body as { event_name?: unknown }).event_name !== 'string' ||
      !(body as { event_name: string }).event_name
    ) {
      return HttpResponse.json(apiError("Field 'event_name' is required"), {
        status: 400,
      })
    }
    const eventName = (body as { event_name: string }).event_name
    return HttpResponse.json(
      successFor<typeof triggerMeeting>([
        buildMeeting({
          meeting_id: `meeting-${eventName}`,
          meeting_type_name: eventName,
        }),
      ]),
    )
  }),
]
