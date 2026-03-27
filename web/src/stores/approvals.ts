import { create } from 'zustand'
import * as approvalsApi from '@/api/endpoints/approvals'
import { getErrorMessage } from '@/utils/errors'
import type {
  ApprovalFilters,
  ApprovalResponse,
  ApproveRequest,
  RejectRequest,
  WsEvent,
} from '@/api/types'

interface ApprovalsState {
  // Data
  approvals: ApprovalResponse[]
  selectedApproval: ApprovalResponse | null
  total: number

  // Loading
  loading: boolean
  loadingDetail: boolean
  error: string | null

  // CRUD
  fetchApprovals: (filters?: ApprovalFilters) => Promise<void>
  fetchApproval: (id: string) => Promise<void>
  approveOne: (id: string, data?: ApproveRequest) => Promise<ApprovalResponse>
  rejectOne: (id: string, data: RejectRequest) => Promise<ApprovalResponse>

  // Real-time
  handleWsEvent: (event: WsEvent) => void

  // Optimistic helpers
  pendingTransitions: Set<string>
  optimisticApprove: (id: string) => () => void
  optimisticReject: (id: string) => () => void
  upsertApproval: (approval: ApprovalResponse) => void

  // Batch selection
  selectedIds: Set<string>
  toggleSelection: (id: string) => void
  selectAllInGroup: (ids: string[]) => void
  deselectAllInGroup: (ids: string[]) => void
  clearSelection: () => void

  // Batch operations
  batchApprove: (ids: string[], comment?: string) => Promise<{ succeeded: number; failed: number }>
  batchReject: (ids: string[], reason: string) => Promise<{ succeeded: number; failed: number }>
}

const pendingTransitions = new Set<string>()

export const useApprovalsStore = create<ApprovalsState>()((set, get) => ({
  approvals: [],
  selectedApproval: null,
  total: 0,
  loading: false,
  loadingDetail: false,
  error: null,
  pendingTransitions,
  selectedIds: new Set<string>(),

  fetchApprovals: async (filters) => {
    set({ loading: true, error: null })
    try {
      const result = await approvalsApi.listApprovals(filters)
      set({ approvals: result.data, total: result.total, loading: false })
    } catch (err) {
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  fetchApproval: async (id) => {
    set({ loadingDetail: true })
    try {
      const approval = await approvalsApi.getApproval(id)
      set({ selectedApproval: approval, loadingDetail: false })
    } catch (err) {
      set({ loadingDetail: false, error: getErrorMessage(err) })
    }
  },

  approveOne: async (id, data) => {
    const approval = await approvalsApi.approveApproval(id, data)
    get().upsertApproval(approval)
    return approval
  },

  rejectOne: async (id, data) => {
    const approval = await approvalsApi.rejectApproval(id, data)
    get().upsertApproval(approval)
    return approval
  },

  handleWsEvent: (event) => {
    const { payload } = event
    if (payload.approval && typeof payload.approval === 'object' && !Array.isArray(payload.approval)) {
      const candidate = payload.approval as Record<string, unknown>
      if (
        typeof candidate.id === 'string' &&
        typeof candidate.status === 'string' &&
        typeof candidate.title === 'string' &&
        typeof candidate.risk_level === 'string' &&
        typeof candidate.action_type === 'string'
      ) {
        if (pendingTransitions.has(candidate.id)) return
        get().upsertApproval(candidate as unknown as ApprovalResponse)
      } else {
        console.error('[approvals/ws] Received malformed approval payload, skipping upsert', {
          id: candidate.id,
          hasTitle: typeof candidate.title === 'string',
          hasStatus: typeof candidate.status === 'string',
        })
      }
    }
  },

  optimisticApprove: (id) => {
    const prev = get().approvals
    const idx = prev.findIndex((a) => a.id === id)
    if (idx === -1) return () => {}
    pendingTransitions.add(id)
    const oldApproval = prev[idx]!
    const updated = { ...oldApproval, status: 'approved' as const, decided_at: new Date().toISOString() }
    const newApprovals = [...prev]
    newApprovals[idx] = updated
    set({ approvals: newApprovals })
    return () => {
      pendingTransitions.delete(id)
      set({ approvals: prev })
    }
  },

  optimisticReject: (id) => {
    const prev = get().approvals
    const idx = prev.findIndex((a) => a.id === id)
    if (idx === -1) return () => {}
    pendingTransitions.add(id)
    const oldApproval = prev[idx]!
    const updated = { ...oldApproval, status: 'rejected' as const, decided_at: new Date().toISOString() }
    const newApprovals = [...prev]
    newApprovals[idx] = updated
    set({ approvals: newApprovals })
    return () => {
      pendingTransitions.delete(id)
      set({ approvals: prev })
    }
  },

  upsertApproval: (approval) => {
    pendingTransitions.delete(approval.id)
    set((s) => {
      const idx = s.approvals.findIndex((a) => a.id === approval.id)
      const newApprovals = idx === -1 ? [approval, ...s.approvals] : [...s.approvals]
      if (idx !== -1) newApprovals[idx] = approval
      const selectedApproval = s.selectedApproval?.id === approval.id ? approval : s.selectedApproval
      return {
        approvals: newApprovals,
        selectedApproval,
        ...(idx === -1 ? { total: s.total + 1 } : {}),
      }
    })
  },

  toggleSelection: (id) => {
    set((s) => {
      const next = new Set(s.selectedIds)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return { selectedIds: next }
    })
  },

  selectAllInGroup: (ids) => {
    set((s) => {
      const next = new Set(s.selectedIds)
      for (const id of ids) next.add(id)
      return { selectedIds: next }
    })
  },

  deselectAllInGroup: (ids) => {
    set((s) => {
      const next = new Set(s.selectedIds)
      for (const id of ids) next.delete(id)
      return { selectedIds: next }
    })
  },

  clearSelection: () => {
    set({ selectedIds: new Set() })
  },

  batchApprove: async (ids, comment) => {
    const rollbacks: Map<string, () => void> = new Map()

    for (const id of ids) {
      const rollback = get().optimisticApprove(id)
      rollbacks.set(id, rollback)
    }

    const results = await Promise.allSettled(
      ids.map((id) => approvalsApi.approveApproval(id, comment ? { comment } : undefined)),
    )

    let succeeded = 0
    let failed = 0
    for (let i = 0; i < results.length; i++) {
      const result = results[i]!
      const id = ids[i]!
      if (result.status === 'fulfilled') {
        get().upsertApproval(result.value)
        succeeded++
      } else {
        const rollback = rollbacks.get(id)
        if (rollback) rollback()
        failed++
      }
    }

    get().clearSelection()
    return { succeeded, failed }
  },

  batchReject: async (ids, reason) => {
    const rollbacks: Map<string, () => void> = new Map()

    for (const id of ids) {
      const rollback = get().optimisticReject(id)
      rollbacks.set(id, rollback)
    }

    const results = await Promise.allSettled(
      ids.map((id) => approvalsApi.rejectApproval(id, { reason })),
    )

    let succeeded = 0
    let failed = 0
    for (let i = 0; i < results.length; i++) {
      const result = results[i]!
      const id = ids[i]!
      if (result.status === 'fulfilled') {
        get().upsertApproval(result.value)
        succeeded++
      } else {
        const rollback = rollbacks.get(id)
        if (rollback) rollback()
        failed++
      }
    }

    get().clearSelection()
    return { succeeded, failed }
  },
}))
