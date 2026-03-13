import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as approvalsApi from '@/api/endpoints/approvals'
import { getErrorMessage } from '@/utils/errors'
import type { ApprovalItem, ApprovalFilters, ApproveRequest, RejectRequest, WsEvent } from '@/api/types'

export const useApprovalStore = defineStore('approvals', () => {
  const approvals = ref<ApprovalItem[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const activeFilters = ref<ApprovalFilters | undefined>(undefined)

  const pendingCount = computed(() => approvals.value.filter((a) => a.status === 'pending').length)

  async function fetchApprovals(filters?: ApprovalFilters) {
    loading.value = true
    error.value = null
    activeFilters.value = filters ? { ...filters } : undefined
    try {
      const result = await approvalsApi.listApprovals(filters)
      approvals.value = result.data
      total.value = result.total
    } catch (err) {
      error.value = getErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  async function approve(id: string, data?: ApproveRequest): Promise<ApprovalItem | null> {
    error.value = null
    try {
      const updated = await approvalsApi.approveApproval(id, data)
      approvals.value = approvals.value.map((a) => (a.id === id ? updated : a))
      return updated
    } catch (err) {
      error.value = getErrorMessage(err)
      return null
    }
  }

  async function reject(id: string, data: RejectRequest): Promise<ApprovalItem | null> {
    error.value = null
    try {
      const updated = await approvalsApi.rejectApproval(id, data)
      approvals.value = approvals.value.map((a) => (a.id === id ? updated : a))
      return updated
    } catch (err) {
      error.value = getErrorMessage(err)
      return null
    }
  }

  /**
   * Handle a WebSocket approval event.
   *
   * The backend sends a minimal payload with ``approval_id`` (not ``id``).
   * For new submissions, we fetch the full item from the API.
   * For status changes, we update the local status and re-fetch for
   * the complete updated item.
   */
  async function handleWsEvent(event: WsEvent) {
    const payload = event.payload as Record<string, unknown> | null
    if (!payload || typeof payload !== 'object') return
    const approvalId = payload.approval_id
    if (typeof approvalId !== 'string' || !approvalId) return

    switch (event.event_type) {
      case 'approval.submitted':
        if (!approvals.value.some((a) => a.id === approvalId)) {
          try {
            const item = await approvalsApi.getApproval(approvalId)
            if (!activeFilters.value) {
              approvals.value = [item, ...approvals.value]
              total.value++
            }
          } catch {
            // Item may have been deleted or expired between event and fetch
          }
        }
        break
      case 'approval.approved':
      case 'approval.rejected':
      case 'approval.expired':
        try {
          const updated = await approvalsApi.getApproval(approvalId)
          approvals.value = approvals.value.map((a) =>
            a.id === approvalId ? updated : a,
          )
        } catch {
          // Item may have been deleted — remove from local list
          approvals.value = approvals.value.filter((a) => a.id !== approvalId)
          total.value = Math.max(0, total.value - 1)
        }
        break
    }
  }

  return {
    approvals,
    total,
    loading,
    error,
    pendingCount,
    fetchApprovals,
    approve,
    reject,
    handleWsEvent,
  }
})
