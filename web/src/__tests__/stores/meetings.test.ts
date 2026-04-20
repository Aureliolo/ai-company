import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { useMeetingsStore, _resetRequestSeqs } from '@/stores/meetings'
import { makeMeeting } from '../helpers/factories'
import { apiError, apiSuccess, paginatedFor } from '@/mocks/handlers'
import type { listMeetings } from '@/api/endpoints/meetings'
import { server } from '@/test-setup'
import type { MeetingResponse } from '@/api/types/meetings'
import type { WsEvent } from '@/api/types/websocket'

function paginated(
  data: MeetingResponse[],
  meta: Partial<{ total: number; offset: number; limit: number }> = {},
) {
  return paginatedFor<typeof listMeetings>({
    data,
    total: meta.total ?? data.length,
    offset: meta.offset ?? 0,
    limit: meta.limit ?? 100,
  })
}

function resetStore() {
  _resetRequestSeqs()
  useMeetingsStore.setState({
    meetings: [],
    selectedMeeting: null,
    total: 0,
    loading: false,
    loadingDetail: false,
    error: null,
    detailError: null,
    triggering: false,
  })
}

beforeEach(() => {
  resetStore()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('fetchMeetings', () => {
  it('sets loading and stores results', async () => {
    const items = [makeMeeting('1'), makeMeeting('2')]
    server.use(
      http.get('/api/v1/meetings', () => HttpResponse.json(paginated(items))),
    )

    await useMeetingsStore.getState().fetchMeetings()

    const state = useMeetingsStore.getState()
    expect(state.loading).toBe(false)
    expect(state.meetings).toHaveLength(2)
    expect(state.total).toBe(2)
    expect(state.error).toBeNull()
  })

  it('sets error on failure', async () => {
    server.use(
      http.get('/api/v1/meetings', () =>
        HttpResponse.json(apiError('Network error')),
      ),
    )

    await useMeetingsStore.getState().fetchMeetings()

    const state = useMeetingsStore.getState()
    expect(state.loading).toBe(false)
    expect(state.error).toBe('Network error')
  })

  it('passes filters to API as query params', async () => {
    const captured: { params: URLSearchParams | null } = { params: null }
    server.use(
      http.get('/api/v1/meetings', ({ request }) => {
        captured.params = new URL(request.url).searchParams
        return HttpResponse.json(paginated([]))
      }),
    )

    await useMeetingsStore
      .getState()
      .fetchMeetings({ status: 'completed', limit: 50 })

    expect(captured.params?.get('status')).toBe('completed')
    expect(captured.params?.get('limit')).toBe('50')
  })

  it('syncs selectedMeeting with fresh data', async () => {
    const old = makeMeeting('1', { status: 'in_progress' })
    useMeetingsStore.setState({ selectedMeeting: old })

    const fresh = makeMeeting('1', { status: 'completed' })
    server.use(
      http.get('/api/v1/meetings', () => HttpResponse.json(paginated([fresh]))),
    )

    await useMeetingsStore.getState().fetchMeetings()

    expect(useMeetingsStore.getState().selectedMeeting?.status).toBe('completed')
  })

  it('rejects stale responses when a newer fetch starts', async () => {
    const staleItems = [makeMeeting('stale')]
    const freshItems = [makeMeeting('fresh')]

    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    let callIndex = 0
    server.use(
      http.get('/api/v1/meetings', async () => {
        const thisCall = callIndex++
        if (thisCall === 0) {
          await gate
          return HttpResponse.json(paginated(staleItems))
        }
        return HttpResponse.json(paginated(freshItems))
      }),
    )

    const firstPromise = useMeetingsStore.getState().fetchMeetings()
    const secondPromise = useMeetingsStore.getState().fetchMeetings()

    await secondPromise
    expect(useMeetingsStore.getState().meetings[0]!.meeting_id).toBe('fresh')

    release()
    await firstPromise

    expect(useMeetingsStore.getState().meetings[0]!.meeting_id).toBe('fresh')
    expect(useMeetingsStore.getState().meetings).toHaveLength(1)
  })
})

describe('fetchMeeting', () => {
  it('sets loadingDetail and stores result', async () => {
    const meeting = makeMeeting('1')
    server.use(
      http.get('/api/v1/meetings/:id', () =>
        HttpResponse.json(apiSuccess(meeting)),
      ),
    )

    await useMeetingsStore.getState().fetchMeeting('1')

    const state = useMeetingsStore.getState()
    expect(state.loadingDetail).toBe(false)
    expect(state.selectedMeeting).toEqual(meeting)
    expect(state.detailError).toBeNull()
  })

  it('sets detailError on failure', async () => {
    server.use(
      http.get('/api/v1/meetings/:id', () =>
        HttpResponse.json(apiError('Not found')),
      ),
    )

    await useMeetingsStore.getState().fetchMeeting('missing')

    const state = useMeetingsStore.getState()
    expect(state.loadingDetail).toBe(false)
    expect(state.detailError).toBe('Not found')
  })

  it('rejects stale detail responses when a newer fetch starts', async () => {
    const staleMeeting = makeMeeting('stale')
    const freshMeeting = makeMeeting('fresh')

    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    server.use(
      http.get('/api/v1/meetings/:id', async ({ params }) => {
        if (params.id === 'stale') {
          await gate
          return HttpResponse.json(apiSuccess(staleMeeting))
        }
        return HttpResponse.json(apiSuccess(freshMeeting))
      }),
    )

    const firstPromise = useMeetingsStore.getState().fetchMeeting('stale')
    const secondPromise = useMeetingsStore.getState().fetchMeeting('fresh')

    await secondPromise
    expect(useMeetingsStore.getState().selectedMeeting?.meeting_id).toBe('fresh')

    release()
    await firstPromise

    expect(useMeetingsStore.getState().selectedMeeting?.meeting_id).toBe('fresh')
  })
})

describe('triggerMeeting', () => {
  it('calls API and prepends results', async () => {
    const existing = makeMeeting('old')
    useMeetingsStore.setState({ meetings: [existing], total: 1 })

    const triggered = [makeMeeting('new')]
    let requestBody: unknown = null
    server.use(
      http.post('/api/v1/meetings/trigger', async ({ request }) => {
        requestBody = await request.json()
        return HttpResponse.json(apiSuccess(triggered))
      }),
    )

    const result = await useMeetingsStore
      .getState()
      .triggerMeeting({ event_name: 'test_event' })

    expect(result).toHaveLength(1)
    expect(requestBody).toEqual({ event_name: 'test_event' })
    const state = useMeetingsStore.getState()
    expect(state.meetings).toHaveLength(2)
    expect(state.meetings[0]!.meeting_id).toBe('new')
    expect(state.total).toBe(2)
    expect(state.triggering).toBe(false)
  })

  it('re-throws on failure and resets triggering', async () => {
    server.use(
      http.post('/api/v1/meetings/trigger', () =>
        HttpResponse.json(apiError('Trigger failed')),
      ),
    )

    await expect(
      useMeetingsStore.getState().triggerMeeting({ event_name: 'bad_event' }),
    ).rejects.toThrow('Trigger failed')

    const state = useMeetingsStore.getState()
    expect(state.triggering).toBe(false)
  })
})

describe('handleWsEvent', () => {
  it('upserts meeting from valid payload', () => {
    const meeting = makeMeeting('ws-1')
    const event: WsEvent = {
      channel: 'meetings',
      event_type: 'meeting.completed',
      payload: { meeting },
      timestamp: new Date().toISOString(),
    }

    useMeetingsStore.getState().handleWsEvent(event)

    expect(useMeetingsStore.getState().meetings).toHaveLength(1)
    expect(useMeetingsStore.getState().meetings[0]!.meeting_id).toBe('ws-1')
  })

  it('skips malformed payload missing required fields', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const event: WsEvent = {
      channel: 'meetings',
      event_type: 'meeting.completed',
      payload: { meeting: { meeting_id: 'bad' } },
      timestamp: new Date().toISOString(),
    }

    useMeetingsStore.getState().handleWsEvent(event)

    expect(useMeetingsStore.getState().meetings).toHaveLength(0)
    expect(consoleSpy).toHaveBeenCalledOnce()
    consoleSpy.mockRestore()
  })

  it('ignores event without meeting field', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const event: WsEvent = {
      channel: 'meetings',
      event_type: 'meeting.completed',
      payload: { other: 'data' },
      timestamp: new Date().toISOString(),
    }

    useMeetingsStore.getState().handleWsEvent(event)

    expect(useMeetingsStore.getState().meetings).toHaveLength(0)
    expect(warnSpy).toHaveBeenCalledOnce()
    warnSpy.mockRestore()
  })

  it('ignores event where meeting is an array', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const event: WsEvent = {
      channel: 'meetings',
      event_type: 'meeting.completed',
      payload: { meeting: [makeMeeting('arr')] },
      timestamp: new Date().toISOString(),
    }

    useMeetingsStore.getState().handleWsEvent(event)

    expect(useMeetingsStore.getState().meetings).toHaveLength(0)
    expect(warnSpy).toHaveBeenCalledOnce()
    warnSpy.mockRestore()
  })

  it('ignores event where meeting is a primitive', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const event: WsEvent = {
      channel: 'meetings',
      event_type: 'meeting.completed',
      payload: { meeting: 'not-an-object' },
      timestamp: new Date().toISOString(),
    }

    useMeetingsStore.getState().handleWsEvent(event)

    expect(useMeetingsStore.getState().meetings).toHaveLength(0)
    expect(warnSpy).toHaveBeenCalledOnce()
    warnSpy.mockRestore()
  })
})

describe('upsertMeeting', () => {
  it('inserts new meeting at the beginning', () => {
    const existing = makeMeeting('1')
    useMeetingsStore.setState({ meetings: [existing], total: 1 })

    const newMeeting = makeMeeting('2')
    useMeetingsStore.getState().upsertMeeting(newMeeting)

    const state = useMeetingsStore.getState()
    expect(state.meetings).toHaveLength(2)
    expect(state.meetings[0]!.meeting_id).toBe('2')
    expect(state.total).toBe(2)
  })

  it('updates existing meeting in place', () => {
    const existing = makeMeeting('1', { status: 'in_progress' })
    useMeetingsStore.setState({ meetings: [existing], total: 1 })

    const updated = makeMeeting('1', { status: 'completed' })
    useMeetingsStore.getState().upsertMeeting(updated)

    const state = useMeetingsStore.getState()
    expect(state.meetings).toHaveLength(1)
    expect(state.meetings[0]!.status).toBe('completed')
    expect(state.total).toBe(1)
  })

  it('syncs selectedMeeting when IDs match', () => {
    const selected = makeMeeting('1', { status: 'in_progress' })
    useMeetingsStore.setState({
      meetings: [selected],
      selectedMeeting: selected,
      total: 1,
    })

    const updated = makeMeeting('1', { status: 'completed' })
    useMeetingsStore.getState().upsertMeeting(updated)

    expect(useMeetingsStore.getState().selectedMeeting?.status).toBe('completed')
  })

  it('does not change selectedMeeting when IDs differ', () => {
    const selected = makeMeeting('1')
    useMeetingsStore.setState({ selectedMeeting: selected })

    const other = makeMeeting('2')
    useMeetingsStore.getState().upsertMeeting(other)

    expect(useMeetingsStore.getState().selectedMeeting?.meeting_id).toBe('1')
  })
})
