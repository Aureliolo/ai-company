import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import { AnimatePresence } from 'framer-motion'
import { AlertTriangle, ClipboardCheck, WifiOff } from 'lucide-react'
import { MetricCard } from '@/components/ui/metric-card'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useApprovalsData } from '@/hooks/useApprovalsData'
import { useToastStore } from '@/stores/toast'
import {
  filterApprovals,
  groupByRiskLevel,
  type ApprovalPageFilters,
} from '@/utils/approvals'
import { getErrorMessage } from '@/utils/errors'
import { ApprovalFilterBar } from './approvals/ApprovalFilterBar'
import { ApprovalRiskGroupSection } from './approvals/ApprovalRiskGroupSection'
import { ApprovalDetailDrawer } from './approvals/ApprovalDetailDrawer'
import { BatchActionBar } from './approvals/BatchActionBar'
import { ApprovalsSkeleton } from './approvals/ApprovalsSkeleton'
import type { ApprovalRiskLevel } from '@/api/types'

const VALID_STATUSES: ReadonlySet<string> = new Set(['pending', 'approved', 'rejected', 'expired'])
const VALID_RISK_LEVELS: ReadonlySet<string> = new Set(['critical', 'high', 'medium', 'low'])

export default function ApprovalsPage() {
  const {
    approvals,
    selectedApproval,
    loading,
    loadingDetail,
    error,
    wsConnected,
    wsSetupError,
    fetchApproval,
    approveOne,
    rejectOne,
    optimisticApprove,
    selectedIds,
    toggleSelection,
    selectAllInGroup,
    deselectAllInGroup,
    clearSelection,
    batchApprove,
    batchReject,
    detailError,
  } = useApprovalsData()

  const [searchParams, setSearchParams] = useSearchParams()
  const [batchApproveOpen, setBatchApproveOpen] = useState(false)
  const [batchRejectOpen, setBatchRejectOpen] = useState(false)
  const [batchComment, setBatchComment] = useState('')
  const [batchReason, setBatchReason] = useState('')
  const [batchLoading, setBatchLoading] = useState(false)
  const [wasConnected, setWasConnected] = useState(false)

  // Track whether WS was ever connected to avoid flash on initial load
  useEffect(() => {
    if (wsConnected) setWasConnected(true)
  }, [wsConnected])

  // URL-synced filters
  const filters: ApprovalPageFilters = useMemo(() => {
    const rawStatus = searchParams.get('status')
    const rawRisk = searchParams.get('risk')
    return {
      status: rawStatus && VALID_STATUSES.has(rawStatus) ? rawStatus as ApprovalPageFilters['status'] : undefined,
      riskLevel: rawRisk && VALID_RISK_LEVELS.has(rawRisk) ? rawRisk as ApprovalPageFilters['riskLevel'] : undefined,
      actionType: searchParams.get('type') ?? undefined,
      search: searchParams.get('search') ?? undefined,
    }
  }, [searchParams])

  const selectedId = searchParams.get('selected')

  const handleFiltersChange = useCallback((newFilters: ApprovalPageFilters) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      // Replace filter params while preserving the 'selected' param for drawer state
      const sel = next.get('selected')
      // Clear old filter params
      next.delete('status')
      next.delete('risk')
      next.delete('type')
      next.delete('search')
      // Set new ones
      if (newFilters.status) next.set('status', newFilters.status)
      if (newFilters.riskLevel) next.set('risk', newFilters.riskLevel)
      if (newFilters.actionType) next.set('type', newFilters.actionType)
      if (newFilters.search) next.set('search', newFilters.search)
      if (sel) next.set('selected', sel)
      return next
    })
  }, [setSearchParams])

  const handleSelectApproval = useCallback((approvalId: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('selected', approvalId)
      return next
    })
  }, [setSearchParams])

  const handleCloseDrawer = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('selected')
      return next
    })
  }, [setSearchParams])

  // Fetch approval detail when URL selected param changes
  useEffect(() => {
    if (selectedId) {
      fetchApproval(selectedId)
    }
  }, [fetchApproval, selectedId])

  // Single item approve -- optimistic update with rollback on failure
  const handleApproveOne = useCallback(async (id: string) => {
    const rollback = optimisticApprove(id)
    try {
      await approveOne(id)
      useToastStore.getState().add({ variant: 'success', title: 'Approval granted' })
    } catch (err) {
      rollback()
      useToastStore.getState().add({ variant: 'error', title: 'Failed to approve', description: getErrorMessage(err) })
    }
  }, [approveOne, optimisticApprove])

  // Single item reject -- opens drawer for the user to provide a reason
  const handleRejectOne = useCallback(async (id: string) => {
    // For single reject, open the drawer so user can enter reason
    handleSelectApproval(id)
  }, [handleSelectApproval])

  // Close batch dialogs when selection is emptied (e.g., by WS updates or optimistic transitions)
  useEffect(() => {
    if (selectedIds.size === 0) {
      setBatchApproveOpen(false)
      setBatchRejectOpen(false)
      setBatchComment('')
      setBatchReason('')
    }
  }, [selectedIds.size])

  // Batch actions
  const handleBatchApprove = useCallback(async () => {
    setBatchLoading(true)
    const ids = Array.from(selectedIds)
    try {
      const result = await batchApprove(ids, batchComment.trim() || undefined)
      setBatchApproveOpen(false)
      setBatchComment('')
      if (result.failed === 0) {
        useToastStore.getState().add({ variant: 'success', title: `Approved ${result.succeeded} items` })
      } else {
        useToastStore.getState().add({
          variant: 'warning',
          title: `Approved ${result.succeeded} of ${ids.length}. ${result.failed} failed.`,
          description: result.failedReasons.length > 0 ? result.failedReasons.join('; ') : undefined,
        })
      }
    } catch (err) {
      useToastStore.getState().add({ variant: 'error', title: 'Batch approve failed', description: getErrorMessage(err) })
    } finally {
      setBatchLoading(false)
    }
  }, [selectedIds, batchApprove, batchComment])

  const handleBatchReject = useCallback(async () => {
    if (!batchReason.trim()) {
      useToastStore.getState().add({ variant: 'error', title: 'Please provide a rejection reason' })
      return
    }
    setBatchLoading(true)
    const ids = Array.from(selectedIds)
    try {
      const result = await batchReject(ids, batchReason.trim())
      setBatchRejectOpen(false)
      setBatchReason('')
      if (result.failed === 0) {
        useToastStore.getState().add({ variant: 'success', title: `Rejected ${result.succeeded} items` })
      } else {
        useToastStore.getState().add({
          variant: 'warning',
          title: `Rejected ${result.succeeded} of ${ids.length}. ${result.failed} failed.`,
          description: result.failedReasons.length > 0 ? result.failedReasons.join('; ') : undefined,
        })
      }
    } catch (err) {
      useToastStore.getState().add({ variant: 'error', title: 'Batch reject failed', description: getErrorMessage(err) })
    } finally {
      setBatchLoading(false)
    }
  }, [selectedIds, batchReject, batchReason])

  // Derived data
  const filtered = useMemo(() => filterApprovals(approvals, filters), [approvals, filters])
  const grouped = useMemo(() => groupByRiskLevel(filtered), [filtered])
  const pendingCount = useMemo(() => approvals.filter((a) => a.status === 'pending').length, [approvals])

  const actionTypes = useMemo(
    () => [...new Set(approvals.map((a) => a.action_type))].sort(),
    [approvals],
  )

  // Metric cards for pending counts by risk level
  const riskCounts = useMemo(() => {
    const counts: Record<ApprovalRiskLevel, number> = { critical: 0, high: 0, medium: 0, low: 0 }
    for (const a of approvals) {
      if (a.status === 'pending') counts[a.risk_level]++
    }
    return counts
  }, [approvals])

  // Loading state
  if (loading && approvals.length === 0) {
    return <ApprovalsSkeleton />
  }

  const hasFilters = !!(filters.status || filters.riskLevel || filters.actionType || filters.search)

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-foreground">Approvals</h1>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {(wsSetupError || (wasConnected && !wsConnected)) && !loading && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-2 text-sm text-warning">
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      <ApprovalFilterBar
        filters={filters}
        onFiltersChange={handleFiltersChange}
        pendingCount={pendingCount}
        totalCount={approvals.length}
        actionTypes={actionTypes}
      />

      {/* Pending counts by risk level */}
      <StaggerGroup className="grid grid-cols-4 gap-grid-gap max-[1023px]:grid-cols-2">
        <StaggerItem>
          <MetricCard label="Critical" value={riskCounts.critical} className="border-l-2 border-l-danger" />
        </StaggerItem>
        <StaggerItem>
          <MetricCard label="High" value={riskCounts.high} className="border-l-2 border-l-warning" />
        </StaggerItem>
        <StaggerItem>
          <MetricCard label="Medium" value={riskCounts.medium} className="border-l-2 border-l-accent" />
        </StaggerItem>
        <StaggerItem>
          <MetricCard label="Low" value={riskCounts.low} className="border-l-2 border-l-accent-dim" />
        </StaggerItem>
      </StaggerGroup>

      {/* Risk-grouped sections */}
      {grouped.size === 0 && !hasFilters && (
        <EmptyState
          icon={ClipboardCheck}
          title="No approvals"
          description="When agents request approval for actions, they'll appear here."
        />
      )}

      {grouped.size === 0 && hasFilters && (
        <EmptyState
          icon={ClipboardCheck}
          title="No matching approvals"
          description="Try adjusting your filters."
          action={{ label: 'Clear filters', onClick: () => handleFiltersChange({}) }}
        />
      )}

      {[...grouped.entries()].map(([riskLevel, items]) => (
        <ApprovalRiskGroupSection
          key={riskLevel}
          riskLevel={riskLevel}
          items={items}
          selectedIds={selectedIds}
          onSelectAll={selectAllInGroup}
          onDeselectAll={deselectAllInGroup}
          onToggleSelect={toggleSelection}
          onSelect={handleSelectApproval}
          onApprove={handleApproveOne}
          onReject={handleRejectOne}
        />
      ))}

      {/* Detail drawer */}
      <AnimatePresence>
        {!!selectedId && (
          <ApprovalDetailDrawer
            approval={selectedApproval}
            open={!!selectedId}
            onClose={handleCloseDrawer}
            onApprove={async (id, data) => { await approveOne(id, data) }}
            onReject={async (id, data) => { await rejectOne(id, data) }}
            loading={loadingDetail}
            error={detailError}
          />
        )}
      </AnimatePresence>

      {/* Batch action bar */}
      <AnimatePresence>
        {selectedIds.size > 0 && (
          <BatchActionBar
            selectedCount={selectedIds.size}
            onApproveAll={() => setBatchApproveOpen(true)}
            onRejectAll={() => setBatchRejectOpen(true)}
            onClearSelection={clearSelection}
            loading={batchLoading}
          />
        )}
      </AnimatePresence>

      {/* Batch approve dialog */}
      <ConfirmDialog
        open={batchApproveOpen}
        onOpenChange={(o) => { setBatchApproveOpen(o); if (!o) setBatchComment('') }}
        title={`Approve ${selectedIds.size} items`}
        description="This will approve all selected pending approvals."
        confirmLabel="Approve All"
        onConfirm={handleBatchApprove}
        loading={batchLoading}
      >
        <textarea
          value={batchComment}
          onChange={(e) => setBatchComment(e.target.value)}
          placeholder="Optional comment..."
          maxLength={2000}
          className="mt-2 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-foreground outline-none resize-y focus:ring-2 focus:ring-accent min-h-16"
          aria-label="Batch approval comment"
        />
      </ConfirmDialog>

      {/* Batch reject dialog */}
      <ConfirmDialog
        open={batchRejectOpen}
        onOpenChange={(o) => { setBatchRejectOpen(o); if (!o) setBatchReason('') }}
        title={`Reject ${selectedIds.size} items`}
        description="Please provide a reason for rejecting all selected items."
        confirmLabel="Reject All"
        variant="destructive"
        onConfirm={handleBatchReject}
        loading={batchLoading}
      >
        <textarea
          value={batchReason}
          onChange={(e) => setBatchReason(e.target.value)}
          placeholder="Reason for rejection..."
          maxLength={2000}
          className="mt-2 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-foreground outline-none resize-y focus:ring-2 focus:ring-accent min-h-16"
          aria-label="Batch rejection reason"
        />
      </ConfirmDialog>
    </div>
  )
}
