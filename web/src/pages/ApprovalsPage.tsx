import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import { AnimatePresence } from 'framer-motion'
import { AlertTriangle, ClipboardCheck, WifiOff } from 'lucide-react'
import { MetricCard } from '@/components/ui/metric-card'
import { SectionCard } from '@/components/ui/section-card'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useApprovalsData } from '@/hooks/useApprovalsData'
import { useToastStore } from '@/stores/toast'
import {
  filterApprovals,
  getRiskLevelIcon,
  getRiskLevelLabel,
  groupByRiskLevel,
  type ApprovalPageFilters,
} from '@/utils/approvals'
import { ApprovalCard } from './approvals/ApprovalCard'
import { ApprovalFilterBar } from './approvals/ApprovalFilterBar'
import { ApprovalDetailDrawer } from './approvals/ApprovalDetailDrawer'
import { BatchActionBar } from './approvals/BatchActionBar'
import { ApprovalsSkeleton } from './approvals/ApprovalsSkeleton'
import type { ApprovalRiskLevel } from '@/api/types'

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
  } = useApprovalsData()

  const [searchParams, setSearchParams] = useSearchParams()
  const [batchApproveOpen, setBatchApproveOpen] = useState(false)
  const [batchRejectOpen, setBatchRejectOpen] = useState(false)
  const [batchComment, setBatchComment] = useState('')
  const [batchReason, setBatchReason] = useState('')
  const [batchLoading, setBatchLoading] = useState(false)

  // URL-synced filters
  const filters: ApprovalPageFilters = useMemo(() => ({
    status: searchParams.get('status') as ApprovalPageFilters['status'] ?? undefined,
    riskLevel: searchParams.get('risk') as ApprovalPageFilters['riskLevel'] ?? undefined,
    actionType: searchParams.get('type') ?? undefined,
    search: searchParams.get('search') ?? undefined,
  }), [searchParams])

  const selectedId = searchParams.get('selected')

  const handleFiltersChange = useCallback((newFilters: ApprovalPageFilters) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      // Preserve selected
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
    fetchApproval(approvalId)
  }, [setSearchParams, fetchApproval])

  const handleCloseDrawer = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('selected')
      return next
    })
  }, [setSearchParams])

  // Open drawer if URL has selected param on mount
  useEffect(() => {
    if (selectedId && !selectedApproval) {
      fetchApproval(selectedId)
    }
  }, [selectedId]) // eslint-disable-line @eslint-react/exhaustive-deps

  // Single item approve/reject via optimistic update
  const handleApproveOne = useCallback(async (id: string) => {
    const rollback = optimisticApprove(id)
    try {
      await approveOne(id)
      useToastStore.getState().add({ variant: 'success', title: 'Approval granted' })
    } catch {
      rollback()
      useToastStore.getState().add({ variant: 'error', title: 'Failed to approve' })
    }
  }, [approveOne, optimisticApprove])

  const handleRejectOne = useCallback(async (id: string) => {
    // For single reject, open the drawer so user can enter reason
    handleSelectApproval(id)
  }, [handleSelectApproval])

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
        useToastStore.getState().add({ variant: 'warning', title: `Approved ${result.succeeded} of ${ids.length}. ${result.failed} failed.` })
      }
    } catch {
      useToastStore.getState().add({ variant: 'error', title: 'Batch approve failed' })
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
        useToastStore.getState().add({ variant: 'warning', title: `Rejected ${result.succeeded} of ${ids.length}. ${result.failed} failed.` })
      }
    } catch {
      useToastStore.getState().add({ variant: 'error', title: 'Batch reject failed' })
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

      {!wsConnected && !loading && (
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

      {[...grouped.entries()].map(([riskLevel, items]) => {
        const Icon = getRiskLevelIcon(riskLevel)
        const pendingInGroup = items.filter((a) => a.status === 'pending')
        const pendingIds = pendingInGroup.map((a) => a.id)
        const allSelected = pendingIds.length > 0 && pendingIds.every((id) => selectedIds.has(id))

        return (
          <ErrorBoundary key={riskLevel} level="section">
            <SectionCard
              title={`${getRiskLevelLabel(riskLevel)} Approvals`}
              icon={Icon}
              action={
                pendingIds.length > 0 ? (
                  <label className="flex items-center gap-1.5 text-xs text-text-secondary cursor-pointer">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={() => {
                        if (allSelected) {
                          deselectAllInGroup(pendingIds)
                        } else {
                          selectAllInGroup(pendingIds)
                        }
                      }}
                      className="size-3.5 accent-accent"
                    />
                    Select all
                  </label>
                ) : undefined
              }
            >
              <StaggerGroup className="space-y-3">
                {items.map((approval) => (
                  <StaggerItem key={approval.id}>
                    <ApprovalCard
                      approval={approval}
                      selected={selectedIds.has(approval.id)}
                      onSelect={handleSelectApproval}
                      onApprove={handleApproveOne}
                      onReject={handleRejectOne}
                      onToggleSelect={toggleSelection}
                    />
                  </StaggerItem>
                ))}
              </StaggerGroup>
            </SectionCard>
          </ErrorBoundary>
        )
      })}

      {/* Detail drawer */}
      <AnimatePresence>
        {selectedId && selectedApproval && (
          <ApprovalDetailDrawer
            approval={selectedApproval}
            open={!!selectedId}
            onClose={handleCloseDrawer}
            onApprove={approveOne}
            onReject={rejectOne}
            loading={loadingDetail}
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
          className="mt-2 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-foreground outline-none resize-y focus:ring-2 focus:ring-accent min-h-[60px]"
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
          className="mt-2 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-foreground outline-none resize-y focus:ring-2 focus:ring-accent min-h-[60px]"
          aria-label="Batch rejection reason"
        />
      </ConfirmDialog>
    </div>
  )
}
