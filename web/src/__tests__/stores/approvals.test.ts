import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useApprovalsStore, _resetPendingTransitions } from '@/stores/approvals'
import { makeApproval } from '../helpers/factories'
import type { ApprovalResponse, WsEvent } from '@/api/types'

// Mock the API module
vi.mock('@/api/endpoints/approvals', () => ({
  listApprovals: vi.fn(),
  getApproval: vi.fn(),
  approveApproval: vi.fn(),
  rejectApproval: vi.fn(),
}))

async function importApi() {
  return await import('@/api/endpoints/approvals')
}

function resetStore() {
  _resetPendingTransitions()
  useApprovalsStore.setState({
    approvals: [],
    selectedApproval: null,
    total: 0,
    loading: false,
    loadingDetail: false,
    error: null,
    detailError: null,
    selectedIds: new Set(),
  })
}

beforeEach(() => {
  resetStore()
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ── fetchApprovals ──────────────────────────────────────────

describe('fetchApprovals', () => {
  it('sets loading and stores results', async () => {
    const api = await importApi()
    const items = [makeApproval('1'), makeApproval('2')]
    vi.mocked(api.listApprovals).mockResolvedValue({ data: items, total: 2, offset: 0, limit: 200 })

    await useApprovalsStore.getState().fetchApprovals()

    const state = useApprovalsStore.getState()
    expect(state.loading).toBe(false)
    expect(state.approvals).toHaveLength(2)
    expect(state.total).toBe(2)
    expect(state.error).toBeNull()
  })

  it('sets error on failure', async () => {
    const api = await importApi()
    vi.mocked(api.listApprovals).mockRejectedValue(new Error('Network error'))

    await useApprovalsStore.getState().fetchApprovals()

    const state = useApprovalsStore.getState()
    expect(state.loading).toBe(false)
    expect(state.error).toBe('Network error')
  })

  it('passes filters to API', async () => {
    const api = await importApi()
    vi.mocked(api.listApprovals).mockResolvedValue({ data: [], total: 0, offset: 0, limit: 200 })

    await useApprovalsStore.getState().fetchApprovals({ status: 'pending', limit: 50 })

    expect(api.listApprovals).toHaveBeenCalledWith({ status: 'pending', limit: 50 })
  })

  it('preserves optimistic state for items in pendingTransitions', async () => {
    const api = await importApi()
    const item = makeApproval('1')
    useApprovalsStore.setState({ approvals: [item] })

    // Optimistic approve puts id into pendingTransitions
    useApprovalsStore.getState().optimisticApprove('1')
    expect(useApprovalsStore.getState().approvals[0]!.status).toBe('approved')

    // Server returns stale pending data
    vi.mocked(api.listApprovals).mockResolvedValueOnce({
      data: [makeApproval('1', { status: 'pending' })],
      total: 1,
      offset: 0,
      limit: 200,
    })
    await useApprovalsStore.getState().fetchApprovals()

    // Optimistic state should be preserved
    expect(useApprovalsStore.getState().approvals[0]!.status).toBe('approved')
  })
})

// ── fetchApproval ───────────────────────────────────────────

describe('fetchApproval', () => {
  it('sets loadingDetail and stores selected approval', async () => {
    const api = await importApi()
    const approval = makeApproval('1')
    vi.mocked(api.getApproval).mockResolvedValue(approval)

    await useApprovalsStore.getState().fetchApproval('1')

    const state = useApprovalsStore.getState()
    expect(state.loadingDetail).toBe(false)
    expect(state.selectedApproval).toEqual(approval)
  })

  it('sets error on failure', async () => {
    const api = await importApi()
    vi.mocked(api.getApproval).mockRejectedValue(new Error('Not found'))

    await useApprovalsStore.getState().fetchApproval('999')

    expect(useApprovalsStore.getState().loadingDetail).toBe(false)
    expect(useApprovalsStore.getState().detailError).toBe('Not found')
  })
})

// ── approveOne ──────────────────────────────────────────────

describe('approveOne', () => {
  it('calls API and upserts result', async () => {
    const api = await importApi()
    const original = makeApproval('1', { status: 'pending' })
    const approved = makeApproval('1', { status: 'approved', decided_by: 'user', decided_at: '2026-03-27T12:00:00Z' })
    useApprovalsStore.setState({ approvals: [original] })
    vi.mocked(api.approveApproval).mockResolvedValue(approved)

    const result = await useApprovalsStore.getState().approveOne('1', { comment: 'LGTM' })

    expect(result.status).toBe('approved')
    expect(useApprovalsStore.getState().approvals[0]!.status).toBe('approved')
    expect(api.approveApproval).toHaveBeenCalledWith('1', { comment: 'LGTM' })
  })

  it('propagates error when API fails', async () => {
    const api = await importApi()
    vi.mocked(api.approveApproval).mockRejectedValue(new Error('Server error'))

    await expect(useApprovalsStore.getState().approveOne('1')).rejects.toThrow('Server error')
  })
})

// ── rejectOne ───────────────────────────────────────────────

describe('rejectOne', () => {
  it('calls API and upserts result', async () => {
    const api = await importApi()
    const original = makeApproval('1', { status: 'pending' })
    const rejected = makeApproval('1', { status: 'rejected', decision_reason: 'Too risky' })
    useApprovalsStore.setState({ approvals: [original] })
    vi.mocked(api.rejectApproval).mockResolvedValue(rejected)

    const result = await useApprovalsStore.getState().rejectOne('1', { reason: 'Too risky' })

    expect(result.status).toBe('rejected')
    expect(api.rejectApproval).toHaveBeenCalledWith('1', { reason: 'Too risky' })
  })

  it('propagates error when API fails', async () => {
    const api = await importApi()
    vi.mocked(api.rejectApproval).mockRejectedValue(new Error('Server error'))

    await expect(useApprovalsStore.getState().rejectOne('1', { reason: 'x' })).rejects.toThrow('Server error')
  })
})

// ── upsertApproval ──────────────────────────────────────────

describe('upsertApproval', () => {
  it('prepends new approval', () => {
    const existing = makeApproval('1')
    useApprovalsStore.setState({ approvals: [existing], total: 1 })

    const newApproval = makeApproval('2')
    useApprovalsStore.getState().upsertApproval(newApproval)

    const state = useApprovalsStore.getState()
    expect(state.approvals).toHaveLength(2)
    expect(state.approvals[0]!.id).toBe('2')
    expect(state.total).toBe(2)
  })

  it('replaces existing approval', () => {
    const original = makeApproval('1', { status: 'pending' })
    useApprovalsStore.setState({ approvals: [original], total: 1 })

    const updated = makeApproval('1', { status: 'approved' })
    useApprovalsStore.getState().upsertApproval(updated)

    const state = useApprovalsStore.getState()
    expect(state.approvals).toHaveLength(1)
    expect(state.approvals[0]!.status).toBe('approved')
    expect(state.total).toBe(1)
  })

  it('updates selectedApproval when matching', () => {
    const approval = makeApproval('1', { status: 'pending' })
    useApprovalsStore.setState({ approvals: [approval], selectedApproval: approval })

    const updated = makeApproval('1', { status: 'approved' })
    useApprovalsStore.getState().upsertApproval(updated)

    expect(useApprovalsStore.getState().selectedApproval!.status).toBe('approved')
  })

  it('prunes selectedIds when approval leaves pending', () => {
    const approval = makeApproval('1', { status: 'pending' })
    useApprovalsStore.setState({ approvals: [approval], selectedIds: new Set(['1', '2']) })

    const decided = makeApproval('1', { status: 'approved' })
    useApprovalsStore.getState().upsertApproval(decided)

    const ids = useApprovalsStore.getState().selectedIds
    expect(ids.has('1')).toBe(false)
    expect(ids.has('2')).toBe(true)
  })

  it('does not update selectedApproval when not matching', () => {
    const selected = makeApproval('1')
    useApprovalsStore.setState({ approvals: [selected], selectedApproval: selected })

    const other = makeApproval('2')
    useApprovalsStore.getState().upsertApproval(other)

    expect(useApprovalsStore.getState().selectedApproval!.id).toBe('1')
  })
})

// ── optimistic approve/reject ───────────────────────────────

describe('optimisticApprove', () => {
  it('optimistically updates status and returns rollback', () => {
    const approval = makeApproval('1', { status: 'pending' })
    useApprovalsStore.setState({ approvals: [approval] })

    const rollback = useApprovalsStore.getState().optimisticApprove('1')

    expect(useApprovalsStore.getState().approvals[0]!.status).toBe('approved')

    rollback()

    expect(useApprovalsStore.getState().approvals[0]!.status).toBe('pending')
  })

  it('returns no-op for missing approval', () => {
    useApprovalsStore.setState({ approvals: [] })

    const rollback = useApprovalsStore.getState().optimisticApprove('nonexistent')

    expect(typeof rollback).toBe('function')
    rollback() // should not throw
  })
})

describe('optimisticReject', () => {
  it('optimistically updates status and returns rollback', () => {
    const approval = makeApproval('1', { status: 'pending' })
    useApprovalsStore.setState({ approvals: [approval] })

    const rollback = useApprovalsStore.getState().optimisticReject('1')

    expect(useApprovalsStore.getState().approvals[0]!.status).toBe('rejected')

    rollback()

    expect(useApprovalsStore.getState().approvals[0]!.status).toBe('pending')
  })
})

// ── handleWsEvent ───────────────────────────────────────────

describe('handleWsEvent', () => {
  function makeWsEvent(approval: Partial<ApprovalResponse>): WsEvent {
    return {
      event_type: 'approval.submitted',
      channel: 'approvals',
      timestamp: '2026-03-27T12:00:00Z',
      payload: { approval },
    }
  }

  it('upserts valid approval from WS event', () => {
    useApprovalsStore.setState({ approvals: [] })

    const event = makeWsEvent(makeApproval('ws-1'))
    useApprovalsStore.getState().handleWsEvent(event)

    expect(useApprovalsStore.getState().approvals).toHaveLength(1)
    expect(useApprovalsStore.getState().approvals[0]!.id).toBe('ws-1')
  })

  it('ignores events without approval payload', () => {
    useApprovalsStore.setState({ approvals: [] })

    const event: WsEvent = {
      event_type: 'approval.submitted',
      channel: 'approvals',
      timestamp: '2026-03-27T12:00:00Z',
      payload: {},
    }
    useApprovalsStore.getState().handleWsEvent(event)

    expect(useApprovalsStore.getState().approvals).toHaveLength(0)
  })

  it('ignores approval with missing required fields', () => {
    useApprovalsStore.setState({ approvals: [] })

    const event = makeWsEvent({ id: 'x' } as Partial<ApprovalResponse>)
    useApprovalsStore.getState().handleWsEvent(event)

    expect(useApprovalsStore.getState().approvals).toHaveLength(0)
  })

  it('ignores array-typed approval payload', () => {
    useApprovalsStore.setState({ approvals: [] })

    const event: WsEvent = {
      event_type: 'approval.submitted',
      channel: 'approvals',
      timestamp: '2026-03-27T12:00:00Z',
      payload: { approval: [makeApproval('1')] as unknown },
    }
    useApprovalsStore.getState().handleWsEvent(event)

    expect(useApprovalsStore.getState().approvals).toHaveLength(0)
  })

  it('skips when approval is in pendingTransitions', () => {
    const approval = makeApproval('1', { status: 'pending' })
    useApprovalsStore.setState({ approvals: [approval] })

    // Trigger optimistic which adds to pendingTransitions
    useApprovalsStore.getState().optimisticApprove('1')
    expect(useApprovalsStore.getState().approvals[0]!.status).toBe('approved')

    // WS event arrives with old status -- should be skipped
    const event = makeWsEvent(makeApproval('1', { status: 'pending' }))
    useApprovalsStore.getState().handleWsEvent(event)

    // Should still show optimistic status
    expect(useApprovalsStore.getState().approvals[0]!.status).toBe('approved')
  })
})

// ── batch selection ─────────────────────────────────────────

describe('batch selection', () => {
  it('toggleSelection adds and removes', () => {
    useApprovalsStore.getState().toggleSelection('1')
    expect(useApprovalsStore.getState().selectedIds.has('1')).toBe(true)

    useApprovalsStore.getState().toggleSelection('1')
    expect(useApprovalsStore.getState().selectedIds.has('1')).toBe(false)
  })

  it('selectAllInGroup adds all IDs', () => {
    useApprovalsStore.getState().selectAllInGroup(['1', '2', '3'])
    expect(useApprovalsStore.getState().selectedIds.size).toBe(3)
  })

  it('deselectAllInGroup removes group IDs', () => {
    useApprovalsStore.getState().selectAllInGroup(['1', '2', '3', '4'])
    useApprovalsStore.getState().deselectAllInGroup(['2', '3'])
    const ids = useApprovalsStore.getState().selectedIds
    expect(ids.size).toBe(2)
    expect(ids.has('1')).toBe(true)
    expect(ids.has('4')).toBe(true)
  })

  it('clearSelection empties the set', () => {
    useApprovalsStore.getState().selectAllInGroup(['1', '2'])
    useApprovalsStore.getState().clearSelection()
    expect(useApprovalsStore.getState().selectedIds.size).toBe(0)
  })
})

// ── batch operations ────────────────────────────────────────

describe('batchApprove', () => {
  it('rejects when batch size exceeds MAX_BATCH_SIZE', async () => {
    const ids = Array.from({ length: 51 }, (_, i) => `id-${i}`)
    const result = await useApprovalsStore.getState().batchApprove(ids)
    expect(result.succeeded).toBe(0)
    expect(result.failed).toBe(51)
    expect(result.failedReasons[0]).toContain('Batch size exceeds maximum of 50')
  })

  it('approves all items and returns success count', async () => {
    const api = await importApi()
    const items = [makeApproval('1'), makeApproval('2')]
    useApprovalsStore.setState({ approvals: items, selectedIds: new Set(['1', '2']) })

    vi.mocked(api.approveApproval).mockImplementation(async (id) =>
      makeApproval(id, { status: 'approved' }),
    )

    const result = await useApprovalsStore.getState().batchApprove(['1', '2'], 'Approved')

    expect(result).toEqual({ succeeded: 2, failed: 0, failedReasons: [] })
    expect(useApprovalsStore.getState().selectedIds.size).toBe(0)
  })

  it('rolls back failed items and returns mixed counts', async () => {
    const api = await importApi()
    const items = [makeApproval('1'), makeApproval('2')]
    useApprovalsStore.setState({ approvals: items, selectedIds: new Set(['1', '2']) })

    vi.mocked(api.approveApproval)
      .mockResolvedValueOnce(makeApproval('1', { status: 'approved' }))
      .mockRejectedValueOnce(new Error('Server error'))

    const result = await useApprovalsStore.getState().batchApprove(['1', '2'])

    expect(result).toEqual({ succeeded: 1, failed: 1, failedReasons: ['Server error'] })
    // Item 2 should be rolled back to pending
    expect(useApprovalsStore.getState().approvals.find((a) => a.id === '2')!.status).toBe('pending')
    // Failed ID should remain selected for retry; successful ID should not
    const ids = useApprovalsStore.getState().selectedIds
    expect(ids.has('2')).toBe(true)
    expect(ids.has('1')).toBe(false)
  })
})

describe('batchReject', () => {
  it('rejects all items and returns success count', async () => {
    const api = await importApi()
    const items = [makeApproval('1'), makeApproval('2')]
    useApprovalsStore.setState({ approvals: items, selectedIds: new Set(['1', '2']) })

    vi.mocked(api.rejectApproval).mockImplementation(async (id) =>
      makeApproval(id, { status: 'rejected' }),
    )

    const result = await useApprovalsStore.getState().batchReject(['1', '2'], 'Too risky')

    expect(result).toEqual({ succeeded: 2, failed: 0, failedReasons: [] })
    expect(api.rejectApproval).toHaveBeenCalledWith('1', { reason: 'Too risky' })
    expect(api.rejectApproval).toHaveBeenCalledWith('2', { reason: 'Too risky' })
  })

  it('rolls back failed items and returns mixed counts', async () => {
    const api = await importApi()
    const items = [makeApproval('1'), makeApproval('2')]
    useApprovalsStore.setState({ approvals: items, selectedIds: new Set(['1', '2']) })

    vi.mocked(api.rejectApproval)
      .mockResolvedValueOnce(makeApproval('1', { status: 'rejected' }))
      .mockRejectedValueOnce(new Error('Server error'))

    const result = await useApprovalsStore.getState().batchReject(['1', '2'], 'Too risky')

    expect(result).toEqual({ succeeded: 1, failed: 1, failedReasons: ['Server error'] })
    expect(useApprovalsStore.getState().approvals.find((a) => a.id === '2')!.status).toBe('pending')
  })
})
