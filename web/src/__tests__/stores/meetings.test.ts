import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useMeetingsStore, _resetRequestSeqs } from '@/stores/meetings'
import { makeMeeting } from '../helpers/factories'
import type { WsEvent } from '@/api/types'

// Mock the API module
vi.mock('@/api/endpoints/meetings', () => ({
  listMeetings: vi.fn(),
  getMeeting: vi.fn(),
  triggerMeeting: vi.fn(),
}))

async function importApi() {
  return await import('@/api/endpoints/meetings')
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
    triggerError: null,
  })
}

beforeEach(() => {
  resetStore()
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

// -- fetchMeetings ----------------------------------------------------------

describe('fetchMeetings', () => {
  it('sets loading and stores results', async () => {
    const api = await importApi()
    const items = [makeMeeting('1'), makeMeeting('2')]
    vi.mocked(api.listMeetings).mockResolvedValue({ data: items, total: 2, offset: 0, limit: 100 })

    await useMeetingsStore.getState().fetchMeetings()

    const state = useMeetingsStore.getState()
    expect(state.loading).toBe(false)
    expect(state.meetings).toHaveLength(2)
    expect(state.total).toBe(2)
    expect(state.error).toBeNull()
  })

  it('sets error on failure', async () => {
    const api = await importApi()
    vi.mocked(api.listMeetings).mockRejectedValue(new Error('Network error'))

    await useMeetingsStore.getState().fetchMeetings()

    const state = useMeetingsStore.getState()
    expect(state.loading).toBe(false)
    expect(state.error).toBe('Network error')
  })

  it('passes filters to API', async () => {
    const api = await importApi()
    vi.mocked(api.listMeetings).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 100 })

    await useMeetingsStore.getState().fetchMeetings({ status: 'completed', limit: 50 })

    expect(api.listMeetings).toHaveBeenCalledWith({ status: 'completed', limit: 50 })
  })

  it('syncs selectedMeeting with fresh data', async () => {
    const api = await importApi()
    const old = makeMeeting('1', { status: 'in_progress' })
    useMeetingsStore.setState({ selectedMeeting: old })

    const fresh = makeMeeting('1', { status: 'completed' })
    vi.mocked(api.listMeetings).mockResolvedValue({ data: [fresh], total: 1, offset: 0, limit: 100 })

    await useMeetingsStore.getState().fetchMeetings()

    expect(useMeetingsStore.getState().selectedMeeting?.status).toBe('completed')
  })
})

// -- fetchMeeting -----------------------------------------------------------

describe('fetchMeeting', () => {
  it('sets loadingDetail and stores result', async () => {
    const api = await importApi()
    const meeting = makeMeeting('1')
    vi.mocked(api.getMeeting).mockResolvedValue(meeting)

    await useMeetingsStore.getState().fetchMeeting('1')

    const state = useMeetingsStore.getState()
    expect(state.loadingDetail).toBe(false)
    expect(state.selectedMeeting).toEqual(meeting)
    expect(state.detailError).toBeNull()
  })

  it('sets detailError on failure', async () => {
    const api = await importApi()
    vi.mocked(api.getMeeting).mockRejectedValue(new Error('Not found'))

    await useMeetingsStore.getState().fetchMeeting('missing')

    const state = useMeetingsStore.getState()
    expect(state.loadingDetail).toBe(false)
    expect(state.detailError).toBe('Not found')
  })
})

// -- triggerMeeting ---------------------------------------------------------

describe('triggerMeeting', () => {
  it('calls API and prepends results', async () => {
    const api = await importApi()
    const existing = makeMeeting('old')
    useMeetingsStore.setState({ meetings: [existing], total: 1 })

    const triggered = [makeMeeting('new')]
    vi.mocked(api.triggerMeeting).mockResolvedValue(triggered)

    const result = await useMeetingsStore.getState().triggerMeeting({ event_name: 'test_event' })

    expect(result).toHaveLength(1)
    const state = useMeetingsStore.getState()
    expect(state.meetings).toHaveLength(2)
    expect(state.meetings[0]!.meeting_id).toBe('new')
    expect(state.total).toBe(2)
    expect(state.triggering).toBe(false)
  })

  it('sets triggerError on failure', async () => {
    const api = await importApi()
    vi.mocked(api.triggerMeeting).mockRejectedValue(new Error('Trigger failed'))

    await expect(useMeetingsStore.getState().triggerMeeting({ event_name: 'bad_event' })).rejects.toThrow()

    const state = useMeetingsStore.getState()
    expect(state.triggering).toBe(false)
    expect(state.triggerError).toBe('Trigger failed')
  })
})

// -- handleWsEvent ----------------------------------------------------------

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

  it('skips malformed payload', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const event: WsEvent = {
      channel: 'meetings',
      event_type: 'meeting.completed',
      payload: { meeting: { meeting_id: 'bad' } },
      timestamp: new Date().toISOString(),
    }

    useMeetingsStore.getState().handleWsEvent(event)

    expect(useMeetingsStore.getState().meetings).toHaveLength(0)
    consoleSpy.mockRestore()
  })

  it('ignores event without meeting field', () => {
    const event: WsEvent = {
      channel: 'meetings',
      event_type: 'meeting.completed',
      payload: { other: 'data' },
      timestamp: new Date().toISOString(),
    }

    useMeetingsStore.getState().handleWsEvent(event)

    expect(useMeetingsStore.getState().meetings).toHaveLength(0)
  })
})

// -- upsertMeeting ----------------------------------------------------------

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
    useMeetingsStore.setState({ meetings: [selected], selectedMeeting: selected, total: 1 })

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
