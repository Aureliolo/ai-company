import { create } from 'zustand'
import * as approvalsApi from '@/api/endpoints/approvals'
import { sanitizeWsString } from '@/stores/notifications'
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
import {
  APPROVAL_RISK_LEVEL_VALUES,
  APPROVAL_STATUS_VALUES,
} from '@/api/types/enums'
import type { WsEvent } from '@/api/types/websocket'

const log = createLogger('approvals')

// Runtime sets derived from the canonical enum tuples in
// `@/api/types/enums`. Building them here rather than re-declaring the
// literal list keeps the validator in lockstep with the type union --
// any drift between the runtime check and the declared enum surfaces
// at compile time.
const APPROVAL_STATUS_SET: ReadonlySet<string> = new Set<string>(APPROVAL_STATUS_VALUES)
const APPROVAL_RISK_LEVEL_SET: ReadonlySet<string> = new Set<string>(APPROVAL_RISK_LEVEL_VALUES)

/** All metadata keys and values must be plain strings. */
function isStringStringRecord(value: unknown): value is Record<string, string> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  for (const [k, v] of Object.entries(value)) {
    if (typeof k !== 'string' || typeof v !== 'string') return false
  }
  return true
}

/**
 * Type predicate: a WS payload object satisfies the {@link ApprovalResponse}
 * shape so consumers can use it without a cast. Enum-typed fields
 * (``status``, ``risk_level``) are validated against their declared
 * unions, and ``metadata`` must be a plain ``Record<string, string>``
 * (the contract on ``ApprovalResponse``) so malformed payloads can't
 * smuggle illegal values or non-string entries into the store.
 */
function isApprovalShape(
  c: Record<string, unknown>,
): c is Record<string, unknown> & ApprovalResponse {
  return (
    typeof c.id === 'string' &&
    typeof c.status === 'string' &&
    APPROVAL_STATUS_SET.has(c.status) &&
    typeof c.title === 'string' &&
    typeof c.risk_level === 'string' &&
    APPROVAL_RISK_LEVEL_SET.has(c.risk_level) &&
    typeof c.action_type === 'string' &&
    typeof c.description === 'string' &&
    typeof c.requested_by === 'string' &&
    typeof c.created_at === 'string' &&
    isStringStringRecord(c.metadata)
  )
}

/**
 * Return a sanitized copy of an ``ApprovalResponse`` with every
 * untrusted WS-origin string field (identifier, action type,
 * enum-typed labels, timestamps, decision fields, and every metadata
 * entry) routed through ``sanitizeWsString``. The shape guard above
 * has already verified the required fields are non-empty strings at
 * ingress time; structurally required fields fall back to ``''`` if
 * sanitization drops them. Optional string fields preserve their
 * ``null``/``undefined`` signal so downstream code can still branch
 * on presence.
 */
function sanitizeApproval(c: ApprovalResponse): ApprovalResponse {
  const metadata: Record<string, string> = {}
  for (const [key, value] of Object.entries(c.metadata)) {
    const safeKey = sanitizeWsString(key, 64) ?? ''
    const safeValue = sanitizeWsString(value, 512) ?? ''
    if (safeKey) metadata[safeKey] = safeValue
  }
  const sanitizeNullable = (value: string | null, cap: number): string | null =>
    value === null ? null : sanitizeWsString(value, cap) ?? ''
  return {
    ...c,
    id: sanitizeWsString(c.id, 128) ?? '',
    status: (sanitizeWsString(c.status, 64) ?? '') as ApprovalResponse['status'],
    title: sanitizeWsString(c.title, 256) ?? '',
    risk_level:
      (sanitizeWsString(c.risk_level, 64) ?? '') as ApprovalResponse['risk_level'],
    urgency_level:
      (sanitizeWsString(c.urgency_level, 64) ?? '') as ApprovalResponse['urgency_level'],
    action_type: sanitizeWsString(c.action_type, 128) ?? '',
    description: sanitizeWsString(c.description, 2048) ?? '',
    requested_by: sanitizeWsString(c.requested_by, 128) ?? '',
    created_at: sanitizeWsString(c.created_at, 64) ?? '',
    expires_at: sanitizeNullable(c.expires_at, 64),
    decided_by: sanitizeNullable(c.decided_by, 128),
    decided_at: sanitizeNullable(c.decided_at, 64),
    decision_reason: sanitizeNullable(c.decision_reason, 2048),
    task_id: sanitizeNullable(c.task_id, 128),
    metadata,
  }
}

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
      if (isApprovalShape(candidate)) {
        if (pendingTransitions.has(candidate.id)) return
        get().upsertApproval(sanitizeApproval(candidate))
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
