import { useCallback, useState } from 'react'
import { motion } from 'framer-motion'
import { Calendar, Check, Loader2, Shield, Tag, User, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { springDefault, overlayBackdrop } from '@/lib/motion'
import { ApprovalTimeline } from './ApprovalTimeline'
import {
  getApprovalStatusLabel,
  getRiskLevelColor,
  getRiskLevelLabel,
  formatUrgency,
} from '@/utils/approvals'
import { formatDate } from '@/utils/format'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'
import type { ApprovalResponse, ApproveRequest, RejectRequest } from '@/api/types'

export interface ApprovalDetailDrawerProps {
  approval: ApprovalResponse | null
  open: boolean
  onClose: () => void
  onApprove: (id: string, data?: ApproveRequest) => Promise<unknown>
  onReject: (id: string, data: RejectRequest) => Promise<unknown>
  loading?: boolean
}

const PANEL_VARIANTS = {
  initial: { x: '100%', opacity: 0 },
  animate: { x: 0, opacity: 1, transition: springDefault },
  exit: { x: '100%', opacity: 0, transition: { duration: 0.15, ease: 'easeIn' as const } },
}

const RISK_DOT_CLASSES: Record<string, string> = {
  danger: 'bg-danger',
  warning: 'bg-warning',
  accent: 'bg-accent',
  'accent-dim': 'bg-accent-dim',
}

const RISK_BADGE_CLASSES: Record<string, string> = {
  danger: 'border-danger/30 bg-danger/10 text-danger',
  warning: 'border-warning/30 bg-warning/10 text-warning',
  accent: 'border-accent/30 bg-accent/10 text-accent',
  'accent-dim': 'border-accent-dim/30 bg-accent-dim/10 text-accent-dim',
}

export function ApprovalDetailDrawer({
  approval,
  open,
  onClose,
  onApprove,
  onReject,
  loading,
}: ApprovalDetailDrawerProps) {
  const [approveOpen, setApproveOpen] = useState(false)
  const [rejectOpen, setRejectOpen] = useState(false)
  const [comment, setComment] = useState('')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const isPending = approval?.status === 'pending'
  const riskColor = approval ? getRiskLevelColor(approval.risk_level) : 'accent'

  const handleApprove = useCallback(async () => {
    if (!approval) return
    setSubmitting(true)
    try {
      await onApprove(approval.id, comment.trim() ? { comment: comment.trim() } : undefined)
      setApproveOpen(false)
      setComment('')
    } catch (err) {
      useToastStore.getState().add({ variant: 'error', title: 'Failed to approve', description: getErrorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }, [approval, comment, onApprove])

  const handleReject = useCallback(async () => {
    if (!approval) return
    if (!reason.trim()) {
      useToastStore.getState().add({ variant: 'error', title: 'Please provide a rejection reason' })
      return
    }
    setSubmitting(true)
    try {
      await onReject(approval.id, { reason: reason.trim() })
      setRejectOpen(false)
      setReason('')
    } catch (err) {
      useToastStore.getState().add({ variant: 'error', title: 'Failed to reject', description: getErrorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }, [approval, reason, onReject])

  if (!open || !approval) return null

  return (
    <>
      {/* Backdrop */}
      <motion.div
        className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm"
        variants={overlayBackdrop}
        initial="initial"
        animate="animate"
        exit="exit"
        onClick={onClose}
      />

      {/* Panel */}
      <motion.aside
        className="fixed top-0 right-0 z-50 flex h-full w-full max-w-lg flex-col border-l border-border bg-base shadow-lg"
        variants={PANEL_VARIANTS}
        initial="initial"
        animate="animate"
        exit="exit"
        role="dialog"
        aria-label={`Approval detail: ${approval.title}`}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-2">
            <span
              className={cn('size-2 rounded-full', RISK_DOT_CLASSES[riskColor])}
              aria-hidden="true"
            />
            <span
              className={cn(
                'inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium leading-none',
                RISK_BADGE_CLASSES[riskColor],
              )}
            >
              {getRiskLevelLabel(approval.risk_level)}
            </span>
            <span className="text-xs text-text-secondary">
              {getApprovalStatusLabel(approval.status)}
            </span>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close panel">
            <X className="size-4" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-6 animate-spin text-text-muted" />
            </div>
          )}

          {!loading && (
            <>
              {/* Title */}
              <h2 className="text-lg font-semibold text-foreground">{approval.title}</h2>

              {/* Description */}
              {approval.description && (
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    Description
                  </label>
                  <p className="mt-1 text-sm text-text-secondary">{approval.description}</p>
                </div>
              )}

              {/* Timeline */}
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  Timeline
                </label>
                <ApprovalTimeline approval={approval} className="mt-2" />
              </div>

              {/* Metadata grid */}
              <div className="grid grid-cols-2 gap-4 rounded-lg border border-border p-3">
                <MetaField icon={Tag} label="Action Type" value={approval.action_type} />
                <MetaField icon={Shield} label="Risk Level" value={getRiskLevelLabel(approval.risk_level)} />
                <MetaField icon={User} label="Requested By" value={approval.requested_by} />
                <MetaField icon={Calendar} label="Created" value={formatDate(approval.created_at)} />
                {approval.expires_at && (
                  <MetaField icon={Calendar} label="Expires" value={formatUrgency(approval.seconds_remaining)} />
                )}
                {approval.decided_by && (
                  <MetaField icon={User} label="Decided By" value={approval.decided_by} />
                )}
                {approval.decided_at && (
                  <MetaField icon={Calendar} label="Decided At" value={formatDate(approval.decided_at)} />
                )}
              </div>

              {/* Decision reason */}
              {approval.decision_reason && (
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    Reason
                  </label>
                  <p className="mt-1 rounded border border-border bg-surface p-2 text-sm text-text-secondary">
                    {approval.decision_reason}
                  </p>
                </div>
              )}

              {/* Task link */}
              {approval.task_id && (
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    Linked Task
                  </label>
                  <p className="mt-1 font-mono text-xs text-text-secondary">{approval.task_id}</p>
                </div>
              )}

              {/* Metadata */}
              {Object.keys(approval.metadata).length > 0 && (
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    Metadata
                  </label>
                  <dl className="mt-1 space-y-1">
                    {Object.entries(approval.metadata).map(([key, value]) => (
                      <div key={key} className="flex items-center gap-2 text-xs">
                        <dt className="font-mono text-text-muted">{key}:</dt>
                        <dd className="text-text-secondary">{value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer actions */}
        {isPending && (
          <div className="flex items-center justify-end gap-2 border-t border-border px-6 py-3">
            <Button
              size="sm"
              variant="outline"
              className="gap-1 border-success/30 text-success hover:bg-success/10"
              onClick={() => setApproveOpen(true)}
            >
              <Check className="size-3.5" />
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="gap-1 border-danger/30 text-danger hover:bg-danger/10"
              onClick={() => setRejectOpen(true)}
            >
              <X className="size-3.5" />
              Reject
            </Button>
          </div>
        )}
      </motion.aside>

      {/* Approve dialog */}
      <ConfirmDialog
        open={approveOpen}
        onOpenChange={(o) => { setApproveOpen(o); if (!o) setComment('') }}
        title="Approve Action"
        description="Are you sure you want to approve this action?"
        confirmLabel="Approve"
        onConfirm={handleApprove}
        loading={submitting}
      >
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Optional comment..."
          className="mt-2 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-foreground outline-none resize-y focus:ring-2 focus:ring-accent min-h-[60px]"
          aria-label="Approval comment"
        />
      </ConfirmDialog>

      {/* Reject dialog */}
      <ConfirmDialog
        open={rejectOpen}
        onOpenChange={(o) => { setRejectOpen(o); if (!o) setReason('') }}
        title="Reject Action"
        description="Please provide a reason for rejection."
        confirmLabel="Reject"
        variant="destructive"
        onConfirm={handleReject}
        loading={submitting}
      >
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason for rejection..."
          className="mt-2 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-foreground outline-none resize-y focus:ring-2 focus:ring-accent min-h-[60px]"
          aria-label="Rejection reason"
        />
      </ConfirmDialog>
    </>
  )
}

function MetaField({ icon: Icon, label, value }: { icon: typeof Tag; label: string; value: string }) {
  return (
    <div className="flex items-start gap-2">
      <Icon className="mt-0.5 size-3.5 text-text-muted" aria-hidden="true" />
      <div>
        <span className="block text-[10px] text-text-muted">{label}</span>
        <span className="block text-xs text-foreground">{value}</span>
      </div>
    </div>
  )
}
