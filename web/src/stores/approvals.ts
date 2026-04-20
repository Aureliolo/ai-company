import { create } from 'zustand'
import * as approvalsApi from '@/api/endpoints/approvals'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import { createLogger } from '@/lib/logger'
import type {
  ApprovalFilters,
  ApprovalResponse,
  ApproveRequest,
  RejectRequest,
} from '@/api/types/approvals'
import type { WsEvent } from '@/api/types/websocket'

const log = createLogger('approvals')

interface ApprovalsState {
  // Data
  approvals: ApprovalResponse[]
  selectedApproval: ApprovalResponse | null
  total: number

  // Loading
  loading: boolean
  loadingDetail: boolean
  error: string | null
  detailError: string | null

  // CRUD
  fetchApprovals: (filters?: ApprovalFilters) => Promise<void>
  fetchApproval: (id: string) => Promise<void>
  approveOne: (id: string, data?: ApproveRequest) => Promise<ApprovalResponse | null>
  rejectOne: (id: string, data: RejectRequest) => Promise<ApprovalResponse | null>

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
  batchApprove: (ids: string[], comment?: string) => Promise<{ succeeded: number; failed: number; failedReasons: string[] }>
  batchReject: (ids: string[], reason: string) => Promise<{ succeeded: number; failed: number; failedReasons: string[] }>
}

const pendingTransitions = new Set<string>()
const MAX_BATCH_SIZE = 50

/** Clear module-level pendingTransitions -- test-only. */
export function _resetPendingTransitions(): void {
  pendingTransitions.clear()
}

let listRequestSeq = 0
let detailRequestSeq = 0

/** Reset module-level detailRequestSeq -- test-only. */
export function _resetDetailRequestSeq(): void {
  detailRequestSeq = 0
}

export const useApprovalsStore = create<ApprovalsState>()((set, get) => ({
  approvals: [],
  selectedApproval: null,
  total: 0,
  loading: false,
  loadingDetail: false,
  error: null,
  detailError: null,
  pendingTransitions,
  selectedIds: new Set<string>(),

  fetchApprovals: async (filters) => {
    const seq = ++listRequestSeq
    set({ loading: true, error: null })
    try {
      const result = await approvalsApi.listApprovals(filters)
      if (seq !== listRequestSeq) return // stale response
      // Merge: preserve items with pending optimistic transitions
      const merged = result.data.map((serverItem) => {
        if (pendingTransitions.has(serverItem.id)) {
          const existing = get().approvals.find((a) => a.id === serverItem.id)
          return existing ?? serverItem
        }
        return serverItem
      })
      // Prune selectedIds: only keep IDs that are still pending
      const pendingIds = new Set(merged.filter((a) => a.status === 'pending').map((a) => a.id))
      const prevSelected = get().selectedIds
      const prunedSelected = [...prevSelected].some((sid) => !pendingIds.has(sid))
        ? new Set([...prevSelected].filter((sid) => pendingIds.has(sid)))
        : prevSelected
      // Sync selectedApproval with fresh data if drawer is open
      const currentSelected = get().selectedApproval
      const freshSelected = currentSelected ? merged.find((a) => a.id === currentSelected.id) ?? currentSelected : null
      set({ approvals: merged, total: result.total, loading: false, selectedIds: prunedSelected, selectedApproval: freshSelected })
    } catch (err) {
      if (seq !== listRequestSeq) return
      log.warn('Failed to fetch approvals', sanitizeForLog(err))
      set({ loading: false, error: getErrorMessage(err) })
    }
  },

  fetchApproval: async (id) => {
    const seq = ++detailRequestSeq
    set({ loadingDetail: true, detailError: null, selectedApproval: null })
    try {
      const approval = await approvalsApi.getApproval(id)
      if (seq !== detailRequestSeq) return // stale response
      set({ selectedApproval: approval, loadingDetail: false, detailError: null })
    } catch (err) {
      if (seq !== detailRequestSeq) return // stale error
      log.warn('Failed to fetch approval detail', sanitizeForLog(err))
      set({ loadingDetail: false, detailError: getErrorMessage(err) })
    }
  },

  approveOne: async (id, data) => {
    try {
      const approval = await approvalsApi.approveApproval(id, data)
      get().upsertApproval(approval)
      useToastStore.getState().add({
        variant: 'success',
        title: 'Approval granted',
      })
      return approval
    } catch (err) {
      log.error('Approve approval failed', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to approve',
        description: getErrorMessage(err),
      })
      return null
    }
  },

  rejectOne: async (id, data) => {
    try {
      const approval = await approvalsApi.rejectApproval(id, data)
      get().upsertApproval(approval)
      useToastStore.getState().add({
        variant: 'success',
        title: 'Approval rejected',
      })
      return approval
    } catch (err) {
      log.error('Reject approval failed', sanitizeForLog(err))
      useToastStore.getState().add({
        variant: 'error',
        title: 'Failed to reject',
        description: getErrorMessage(err),
      })
      return null
    }
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
        typeof candidate.action_type === 'string' &&
        typeof candidate.description === 'string' &&
        typeof candidate.requested_by === 'string' &&
        typeof candidate.created_at === 'string' &&
        (candidate.metadata === undefined || candidate.metadata === null || (typeof candidate.metadata === 'object' && !Array.isArray(candidate.metadata)))
      ) {
        if (pendingTransitions.has(candidate.id)) return
        get().upsertApproval(candidate as unknown as ApprovalResponse)
      } else {
        log.error('Received malformed approval payload, skipping upsert', {
          id: sanitizeForLog(candidate.id),
          hasTitle: typeof candidate.title === 'string',
          hasStatus: typeof candidate.status === 'string',
        })
      }
    }
  },

  optimisticApprove: (id) => {
    const approvals = get().approvals
    const idx = approvals.findIndex((a) => a.id === id)
    if (idx === -1) {
      log.warn('optimisticApprove: approval not found in store', id)
      return () => {}
    }
    pendingTransitions.add(id)
    const prevSelectedIds = get().selectedIds
    const hadSelection = prevSelectedIds.has(id)
    const newSelectedIds = new Set(prevSelectedIds)
    newSelectedIds.delete(id)
    const oldApproval = approvals[idx]!
    const updated = { ...oldApproval, status: 'approved' as const, decided_at: new Date().toISOString() }
    const newApprovals = [...approvals]
    newApprovals[idx] = updated
    const selectedApproval = get().selectedApproval?.id === id ? updated : get().selectedApproval
    set({ approvals: newApprovals, selectedIds: newSelectedIds, selectedApproval })
    return () => {
      pendingTransitions.delete(id)
      set((s) => {
        const currentApprovals = [...s.approvals]
        const currentIdx = currentApprovals.findIndex((a) => a.id === id)
        if (currentIdx !== -1) currentApprovals[currentIdx] = oldApproval
        const restoredIds = hadSelection ? new Set([...s.selectedIds, id]) : s.selectedIds
        const restoredSelected = s.selectedApproval?.id === id ? oldApproval : s.selectedApproval
        return { approvals: currentApprovals, selectedIds: restoredIds, selectedApproval: restoredSelected }
      })
    }
  },

  optimisticReject: (id) => {
    const approvals = get().approvals
    const idx = approvals.findIndex((a) => a.id === id)
    if (idx === -1) {
      log.warn('optimisticReject: approval not found in store', id)
      return () => {}
    }
    pendingTransitions.add(id)
    const prevSelectedIds = get().selectedIds
    const hadSelection = prevSelectedIds.has(id)
    const newSelectedIds = new Set(prevSelectedIds)
    newSelectedIds.delete(id)
    const oldApproval = approvals[idx]!
    const updated = { ...oldApproval, status: 'rejected' as const, decided_at: new Date().toISOString() }
    const newApprovals = [...approvals]
    newApprovals[idx] = updated
    const selectedApproval = get().selectedApproval?.id === id ? updated : get().selectedApproval
    set({ approvals: newApprovals, selectedIds: newSelectedIds, selectedApproval })
    return () => {
      pendingTransitions.delete(id)
      set((s) => {
        const currentApprovals = [...s.approvals]
        const currentIdx = currentApprovals.findIndex((a) => a.id === id)
        if (currentIdx !== -1) currentApprovals[currentIdx] = oldApproval
        const restoredIds = hadSelection ? new Set([...s.selectedIds, id]) : s.selectedIds
        const restoredSelected = s.selectedApproval?.id === id ? oldApproval : s.selectedApproval
        return { approvals: currentApprovals, selectedIds: restoredIds, selectedApproval: restoredSelected }
      })
    }
  },

  upsertApproval: (approval) => {
    pendingTransitions.delete(approval.id)
    set((s) => {
      const idx = s.approvals.findIndex((a) => a.id === approval.id)
      const newApprovals = idx === -1 ? [approval, ...s.approvals] : [...s.approvals]
      if (idx !== -1) newApprovals[idx] = approval
      const selectedApproval = s.selectedApproval?.id === approval.id ? approval : s.selectedApproval
      const newSelectedIds = approval.status !== 'pending' && s.selectedIds.has(approval.id)
        ? new Set([...s.selectedIds].filter((sid) => sid !== approval.id))
        : s.selectedIds
      return {
        approvals: newApprovals,
        selectedApproval,
        selectedIds: newSelectedIds,
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
    if (ids.length > MAX_BATCH_SIZE) {
      return { succeeded: 0, failed: ids.length, failedReasons: [`Batch size exceeds maximum of ${MAX_BATCH_SIZE}`] }
    }

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
    const failedReasons: string[] = []
    for (let i = 0; i < results.length; i++) {
      const result = results[i]!
      const id = ids[i]!
      if (result.status === 'fulfilled') {
        get().upsertApproval(result.value)
        succeeded++
      } else {
        const rollback = rollbacks.get(id)
        if (rollback) rollback()
        failedReasons.push(getErrorMessage(result.reason))
        failed++
      }
    }

    if (failed === 0) {
      get().clearSelection()
    }
    // (failed IDs are already rolled back and restored to selectedIds by the targeted rollback)
    return { succeeded, failed, failedReasons }
  },

  batchReject: async (ids, reason) => {
    if (ids.length > MAX_BATCH_SIZE) {
      return { succeeded: 0, failed: ids.length, failedReasons: [`Batch size exceeds maximum of ${MAX_BATCH_SIZE}`] }
    }

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
    const failedReasons: string[] = []
    for (let i = 0; i < results.length; i++) {
      const result = results[i]!
      const id = ids[i]!
      if (result.status === 'fulfilled') {
        get().upsertApproval(result.value)
        succeeded++
      } else {
        const rollback = rollbacks.get(id)
        if (rollback) rollback()
        failedReasons.push(getErrorMessage(result.reason))
        failed++
      }
    }

    if (failed === 0) {
      get().clearSelection()
    }
    // (failed IDs are already rolled back and restored to selectedIds by the targeted rollback)
    return { succeeded, failed, failedReasons }
  },
}))
